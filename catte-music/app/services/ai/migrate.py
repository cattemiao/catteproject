"""旧数据多标签迁移脚本（情绪算法 v2）。

把 v1 单标签时代的 ai_predictions（emotion_probs IS NULL）补齐为 20 维
情绪概率向量，让推荐相似度、情绪徽章对新旧数据表现一致。

迁移模式（--mode）：
    template   （默认）用存储的 feature_vector 重建模板伪概率（不依赖网络/模型）
    reanalyze  重新下载试听音频跑 v2 推理（最准确，但慢且依赖网络）
    dry-run    只统计待迁移数量，不写库

幂等性：只处理 emotion_probs IS NULL 的行；--start-id 游标断点续跑；
每批提交一次，中断后从上次进度继续。

用法：
    python -m app.services.ai.migrate --mode template --batch 50
    python -m app.services.ai.migrate --mode reanalyze --limit 20 --start-id 100
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import tempfile
from pathlib import Path

import numpy as np
from sqlalchemy import select

from app.database import async_session_factory
from app.models.prediction import AiPrediction
from app.models.song import Song

logger = logging.getLogger(__name__)

# reanalyze 模式复用的会话（由 migrate() 注入）
_session: object = None


def _template_probs_from_pred(pred: AiPrediction) -> dict[str, float] | None:
    """用存储的 feature_vector 重建 20 维模板伪概率；无特征返回 None。"""
    from app.services.ai import model as ai_model
    from app.services.ai.feature import template_probs

    fv = pred.feature_vector
    if not fv:
        return None
    try:
        keys = sorted(fv, key=lambda k: int(k))
        vec = np.array([float(fv[k]) for k in keys])
    except (ValueError, TypeError):
        return None
    probs = template_probs(vec)
    return {name: round(float(probs.get(name, 0.0)), 4) for name in ai_model.EMOTION_LABELS}


async def _reanalyze(pred: AiPrediction) -> dict | None:
    """重新下载试听音频跑 v2 推理，返回 {probs, primary, confidence, dims, version}。"""
    from app.api.analyze import _classify, _download_preview, _search_preview
    from app.services.ai.feature import extract_features, map_to_dimensions

    song_result = await _session.get(Song, pred.song_id)
    if not song_result:
        return None
    song = song_result

    preview_urls: list[str] = []
    if getattr(song, "platform", "apple") == "netease":
        from app.services.netease import client as netease_client

        try:
            url = await netease_client.get_song_url(None, song.netease_id)
            if url:
                preview_urls.append(url)
        except Exception as exc:
            logger.warning("网易云试听获取失败（%s）: %s", song.title, exc)
    try:
        apple_url = await _search_preview(song.title, song.artist)
        if apple_url:
            preview_urls.append(apple_url)
    except Exception as exc:
        logger.warning("Apple Music 预览搜索失败（%s）: %s", song.title, exc)

    for preview_url in preview_urls:
        suffix = ".mp3" if ".mp3" in preview_url.split("?")[0] else ".m4a"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            await _download_preview(preview_url, tmp_path)
            features = extract_features(tmp_path)
            result, version = _classify(features)
            dims = map_to_dimensions(features)
            return {
                "probs": result["probs"],
                "primary": result["primary"],
                "confidence": result["confidence"],
                "dims": dims,
                "version": version,
            }
        except Exception as exc:
            logger.warning("重分析失败（%s）: %s", song.title, exc)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    return None


async def migrate(mode: str, batch: int, limit: int | None, start_id: int) -> None:
    """执行迁移：id 游标增量扫描 emotion_probs IS NULL 的记录。"""
    global _session
    done = skipped = 0
    last_id = start_id
    async with async_session_factory() as session:
        _session = session
        while True:
            if limit is not None and done + skipped >= limit:
                break
            q = (
                select(AiPrediction)
                .where(
                    AiPrediction.emotion_probs.is_(None),
                    AiPrediction.id > last_id,
                )
                .order_by(AiPrediction.id)
                .limit(batch)
            )
            rows = (await session.execute(q)).scalars().all()
            if not rows:
                break

            for pred in rows:
                last_id = pred.id
                if mode == "reanalyze":
                    result = await _reanalyze(pred)
                    if not result:
                        skipped += 1
                        logger.info("#%d 跳过（无音频/失败）", pred.id)
                        continue
                    pred.emotion_probs = result["probs"]
                    pred.model_version = result["version"]
                    pred.confidence = result["confidence"]
                    from app.models.user import Emotion

                    emo = (
                        await session.execute(
                            select(Emotion).where(Emotion.name == result["primary"])
                        )
                    ).scalar_one_or_none()
                    if emo:
                        pred.emotion_id = emo.id
                    d = result["dims"]
                    pred.loudness, pred.high_freq, pred.rhythm = d[0], d[1], d[2]
                    pred.soundstage, pred.layering = d[3], d[4]
                    pred.soothing, pred.prosody = d[5], d[6]
                else:  # template
                    probs = _template_probs_from_pred(pred)
                    if not probs:
                        skipped += 1
                        logger.info("#%d 跳过（无 feature_vector）", pred.id)
                        continue
                    pred.emotion_probs = probs  # 模板近似，保留原 model_version
                done += 1
                logger.info("#%d 迁移完成: %s", pred.id, mode)

            await session.commit()
            logger.info("批次完成: 累计迁移 %d, 跳过 %d（游标 id=%d）", done, skipped, last_id)

    logger.info("迁移结束: 成功 %d, 跳过 %d", done, skipped)


async def dry_run() -> tuple[int, int]:
    """统计待迁移数量：有 feature_vector（可模板补齐） vs 无特征（仅可重分析）。"""
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(AiPrediction).where(AiPrediction.emotion_probs.is_(None))
            )
        ).scalars().all()
        with_feat = sum(1 for p in rows if p.feature_vector)
    return with_feat, len(rows) - with_feat


def main() -> None:
    parser = argparse.ArgumentParser(description="旧数据多标签迁移（情绪算法 v2）")
    parser.add_argument("--mode", choices=["template", "reanalyze", "dry-run"],
                        default="template", help="迁移模式（默认 template）")
    parser.add_argument("--batch", type=int, default=50, help="每批处理条数")
    parser.add_argument("--limit", type=int, default=None, help="最多处理条数（调试用）")
    parser.add_argument("--start-id", type=int, default=0, help="id 游标起点（断点续跑）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.mode == "dry-run":
        with_feat, no_feat = asyncio.run(dry_run())
        print(f"待迁移: {with_feat} 条可用模板补齐, {no_feat} 条仅可重分析")
        return

    asyncio.run(migrate(args.mode, args.batch, args.limit, args.start_id))


if __name__ == "__main__":
    main()
