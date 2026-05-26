"""L2 이미지 분석 — 로고 pHash 유사도 비교"""
from __future__ import annotations

import io
import logging

import httpx

logger = logging.getLogger(__name__)

_HAMMING_THRESHOLD = 10  # 해밍 거리 10 이하 → 의심


class LogoSimilarityEngine:
    """고객 로고를 pHash로 등록하고 수집 이미지와 유사도를 비교한다."""

    def __init__(self) -> None:
        # {profile_id: [ImageHash, ...]}
        self._registry: dict[int, list] = {}

    # ── 등록 ────────────────────────────────────────────────────────

    def register_logo(self, profile_id: int, image) -> object:
        """PIL.Image로 로고를 등록하고 pHash를 반환한다."""
        import imagehash
        h = imagehash.phash(image)
        hashes = self._registry.setdefault(profile_id, [])
        if h not in hashes:
            hashes.append(h)
            logger.debug("Logo registered: profile=%s hash=%s", profile_id, h)
        return h

    async def register_logo_from_url(self, profile_id: int, url: str) -> object | None:
        """URL에서 이미지를 받아 pHash로 등록한다. 실패 시 None 반환."""
        try:
            from PIL import Image
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            return self.register_logo(profile_id, img)
        except Exception as e:
            logger.warning("Logo URL 등록 실패 (profile=%s url=%s): %s", profile_id, url, e)
            return None

    # ── 비교 ────────────────────────────────────────────────────────

    def compare(self, image) -> dict:
        """
        PIL.Image를 등록된 모든 로고와 비교한다.

        Returns:
            is_suspicious: 해밍 거리 ≤ 10 이면 True
            hamming_distance: 최소 해밍 거리 (등록된 로고 없으면 None)
            matched_profile_id: 가장 유사한 프로파일 ID (의심스러울 때만)
            target_hash: 대상 이미지의 pHash 문자열
        """
        import imagehash
        target_hash = imagehash.phash(image)
        best_distance: int | float = float("inf")
        best_profile: int | None = None

        for profile_id, hashes in self._registry.items():
            for h in hashes:
                dist = target_hash - h
                if dist < best_distance:
                    best_distance = dist
                    best_profile = profile_id

        has_registry = bool(self._registry)
        is_suspicious = has_registry and best_distance <= _HAMMING_THRESHOLD

        return {
            "is_suspicious": is_suspicious,
            "hamming_distance": int(best_distance) if has_registry else None,
            "matched_profile_id": best_profile if is_suspicious else None,
            "target_hash": str(target_hash),
        }

    async def compare_from_url(self, url: str) -> dict:
        """URL에서 이미지를 받아 등록된 로고와 비교한다. 오류 시 안전 기본값 반환."""
        try:
            from PIL import Image
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            return self.compare(img)
        except Exception as e:
            logger.warning("이미지 URL 비교 실패 (%s): %s", url, e)
            return {
                "is_suspicious": False,
                "hamming_distance": None,
                "matched_profile_id": None,
                "target_hash": None,
            }

    # ── 유틸 ────────────────────────────────────────────────────────

    def registered_profile_ids(self) -> list[int]:
        return list(self._registry.keys())

    def clear(self, profile_id: int | None = None) -> None:
        if profile_id is None:
            self._registry.clear()
        else:
            self._registry.pop(profile_id, None)


    async def register_from_profile(self, profile) -> None:
        """프로파일 저장 시 자동 호출 — 로고 + 임직원 사진 pHash 일괄 등록."""
        if profile.logo_url:
            result = await self.register_logo_from_url(profile.profile_id, profile.logo_url)
            if result:
                logger.info("로고 등록 완료: profile=%s", profile.profile_id)

        for exec_info in profile.executives:
            photo_url = exec_info.get("photo_url")
            if photo_url:
                result = await self.register_logo_from_url(profile.profile_id, photo_url)
                if result:
                    logger.debug("임직원 사진 등록: %s (%s)", exec_info["name"], photo_url)

    async def compare_all(self, image_urls: list[str], profile) -> dict:
        """
        수집된 이미지 목록을 등록된 자산(로고+임직원사진) 전부와 비교한다.

        Returns:
            {logo: [...], executive: [...], most_suspicious: {...}|None}
        """
        results: dict = {"logo": [], "executive": [], "most_suspicious": None}
        max_score = 0.0

        if not image_urls:
            return results

        if not self._registry.get(profile.profile_id):
            # 아직 등록 안 됐으면 자동 등록
            await self.register_from_profile(profile)

        for img_url in image_urls:
            comparison = await self.compare_from_url(img_url)
            if not comparison.get("is_suspicious"):
                continue

            dist = comparison.get("hamming_distance") or 99
            similarity = max(0.0, 1.0 - dist / 64.0)

            entry = {"image_url": img_url, "similarity": similarity, "hamming_distance": dist}

            if similarity > max_score:
                max_score = similarity
                results["most_suspicious"] = {**entry, "type": "logo"}

            if similarity > 0.5:
                results["logo"].append(entry)

        return results


logo_engine = LogoSimilarityEngine()
