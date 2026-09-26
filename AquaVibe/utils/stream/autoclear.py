# Authored By Dev © 2025
import os

from config import autoclean


async def auto_clean(popped):
    try:
        rem = popped["file"]
        autoclean.remove(rem)
        count = autoclean.count(rem)
        if count == 0:
            if not any(marker in rem for marker in ("vid_", "live_", "index_")):
                try:
                    os.remove(rem)
                except Exception:
                    pass
    except Exception:
        pass
