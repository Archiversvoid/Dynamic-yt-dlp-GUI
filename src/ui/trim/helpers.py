"""Small helpers for the TrimLoad tab: time formatting/parsing, picking the preview stream, the invalid-input shake."""
from src.core.downloader import _is_audio_only_url


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
