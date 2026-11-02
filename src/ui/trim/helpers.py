"""Small helpers for the TrimLoad tab: time formatting/parsing, picking the preview stream, the invalid-input shake."""
from src.core.downloader import _is_audio_only_url, snap_mp3_bitrate


def format_time_str(seconds):
    seconds = max(0, float(seconds))
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_time_str(time_str):
    try:
        parts = [float(p) for p in time_str.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:
            return parts[0]
    except Exception:
        pass
    return -1.0


def select_preview_stream(info, url):
    if not isinstance(info, dict):
        return None, None, False

    formats = info.get('formats') or []
    is_audio_platform = _is_audio_only_url(url)

    if not formats:
        stream_url = info.get('url')
        if stream_url:
            vcodec = info.get('vcodec')
            is_audio = is_audio_platform or (vcodec == 'none')
            return stream_url, 0, is_audio
        return None, None, False

    valid = [f for f in formats if f.get('url') and str(f.get('url')).startswith('http')]
    vids = [f for f in valid if f.get('vcodec') not in ('none', None)]

    all_audio_only = bool(valid) and all(f.get('vcodec') == 'none' for f in valid)
    is_pure_audio = is_audio_platform or all_audio_only

    if is_pure_audio:
        auds = [f for f in valid if f.get('acodec') not in ('none', None)]
        if auds:
            best_aud = sorted(auds, key=lambda x: x.get('abr') or 0, reverse=True)[0]
            return best_aud.get('url'), 0, True
        fallback = [f for f in valid]
        if fallback:
            return fallback[0].get('url'), 0, True
        return None, None, True

    def vid_score(f):
        s = 0
        h = f.get('height') or 9999
        vcodec = (f.get('vcodec') or '').lower()
        ext = (f.get('ext') or '').lower()
        
        if 'av1' in vcodec or 'av01' in vcodec:
            s -= 100000
        if 'vp9' in vcodec or 'vp09' in vcodec:
            s -= 20000

        if 'avc' in vcodec or 'h264' in vcodec: 
            s += 50000
        if ext == 'mp4': 
            s += 20000

        if 0 < h <= 720:
            s += (10000 - h)
            
        return s

    if vids:
        best_vid = max(vids, key=vid_score)
    elif valid:
        best_vid = valid[0]
    else:
        return None, None, False

    return best_vid.get('url'), best_vid.get('height') or 0, False


from src.ui.helpers import jiggle_widget as _shared_jiggle

_TRIM_JIGGLE = (-10, 10, -7, 7, -4, 4, -2, 2, 0)      # a little gentler than the shake on Home


def jiggle_widget(widget):
    """The 'invalid input' shake used in this tab."""
    _shared_jiggle(widget, _TRIM_JIGGLE)


def is_live_info(info):
    """A live stream, or one that is scheduled but hasn't started - the same rule Home uses."""
    return bool(info) and (bool(info.get("is_live")) or info.get("live_status") in ("is_live", "is_upcoming"))


def live_message(info):
    if (info or {}).get("live_status") == "is_upcoming":
        return "This live stream hasn't started yet. Paste the link again once it has finished."
    return "Live streams can't be trimmed. Paste a link to a finished video instead."


def video_quality_items(info):
    """[(label, format)] for Video mode: one entry per available resolution, best first."""
    items, seen = [], set()
    video_formats = [f for f in (info.get("formats") or []) if f.get("vcodec") not in ("none", None)]
    for f in reversed(video_formats):
        h = f.get("height")
        if h and h not in seen:
            seen.add(h)
            items.append((f"{h}p", f))
    return items or [("Best", None)]


def audio_bitrate_items(info):
    """[(label, {"format_id", "kbps"})] for Audio mode: the MP3 bitrates this media can really deliver,
    best first. Downloads are encoded to MP3, so these are MP3 steps (a stream reporting 129.5 kbps
    shows as 128). With no bitrate information at all, the usual ladder is offered."""
    fmts = [f for f in (info.get("formats") or []) if f.get("acodec") not in (None, "none") and f.get("ext") != "mhtml"]
    pure = [f for f in fmts if f.get("vcodec") in (None, "none")]
    items, seen = [], set()
    for f in (pure or fmts):
        raw = f.get("abr") or (f.get("tbr") if f in pure else None)      # a muxed stream's tbr includes the video
        if not raw:
            continue
        kbps = snap_mp3_bitrate(raw)
        if kbps in seen:
            continue
        seen.add(kbps)
        items.append((f"{kbps} kbps", {"format_id": f.get("format_id"), "kbps": kbps}))
    items.sort(key=lambda it: it[1]["kbps"], reverse=True)
    return items or [(f"{br} kbps", {"format_id": None, "kbps": br}) for br in (320, 256, 192, 128, 96, 64)]
