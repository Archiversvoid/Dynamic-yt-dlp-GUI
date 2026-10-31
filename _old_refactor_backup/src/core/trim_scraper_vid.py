"""
Video trimmer scraper module for Dynamic 2.
"""
import yt_dlp

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

def scrape(url):
    res = {
        "ok": False, "error": "Unknown error", "title": "", 
        "duration": 0, "uploader": "", "thumbnail": "", 
        "video_formats": [], "stream_url": "", "stream_headers": {}
    }
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'skip_download': True,
        'noplaylist': True, 'user_agent': DEFAULT_UA,
        'extractor_args': {'youtube': ['lang=en', 'player_client=web']},
        'http_headers': {'Accept-Language': 'en-US,en;q=0.9'}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            inf = ydl.extract_info(url, download=False)
            res["ok"] = True
            res["title"] = inf.get("title", "Unknown Title")
            res["duration"] = inf.get("duration", 0)
            res["uploader"] = inf.get("uploader", "")
            res["thumbnail"] = inf.get("thumbnail", "")
            formats = inf.get('formats') or []
            
            mapped_vids = []
            for f in formats:
                vcodec = f.get("vcodec"); acodec = f.get("acodec"); fid = f.get("format_id")
                if vcodec != "none" and vcodec is not None:
                    h = f.get("height") or 0
                    if h < 144: continue
                    has_audio = acodec != "none" and acodec is not None
                    final_fid = str(fid) if has_audio else f"{fid}+ba/b"
                    lbl = f"{h}p" if h > 0 else str(fid)
                    mapped_vids.append({
                        "format_id": final_fid, "url": f.get("url"), "label": str(lbl),
                        "vcodec": vcodec, "acodec": acodec if has_audio else "none",
                        "height": h, "ext": f.get("ext", ""), "tbr": f.get("tbr") or 0
                    })
            res["video_formats"] = mapped_vids
    except Exception as e:
        res = {"ok": False, "error": f"Video scraping failed: {str(e)}"}
    return res