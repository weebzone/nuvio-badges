"""Check packs/classic.json against player and stream-list text with Java's regex engine."""
import json
import subprocess

PLAYER = {
    "1080p FHD HEVC H.265 H265 x265 10bit AAC 5.1 hi Hindi":
        {"1080p", "HEVC", "10bit", "AAC", "5.1"},
    "2160p 4K UHD HEVC H.265 H265 x265 DV DoVi Dolby Vision HDR HDR10 10bit DD+ DDP EAC3 Atmos 7.1 en English":
        {"4K", "HEVC", "DV · HDR10", "ATMOS DIGITAL+", "7.1"},
    "720p AVC H.264 H264 x264 AAC 2.0":
        {"720p", "AVC", "AAC", "2.0"},
    "1080p FHD HEVC H.265 H265 x265 DTS DTS-HD DTS-HD MA 5.1":
        {"1080p", "HEVC", "DTS-HD MA", "5.1"},
}
# Stream list text from the screenshot: must keep working and keep only the highest layout.
STREAM = {
    "Frankenstein (2025) 1080p 10bit NF BluRay HEVC x265 [ Hindi AAC5.1 + English AAC7.1 ] ESub ~ MoviesMod.mkv 2.87GB\\nH.265 10bit AAC 5.1\\nTelegram 1080p Blu-ray":
        {"1080p", "10bit", "HEVC", "AAC", "7.1", "BluRay", "NETFLIX"},
}

pack = json.load(open("packs/classic.json"))
cases = {**PLAYER, **STREAM}
stdin = "\n".join(f"{f['name']}\t{f['pattern']}" for f in pack["filters"]) + "\n--\n" + "\n".join(cases) + "\n"
out = subprocess.run(["java", "Check.java"], input=stdin, capture_output=True, text=True, check=True).stdout.splitlines()
ok = True
for (text, want), got in zip(cases.items(), out):
    got = set(filter(None, got.split("|")))
    missing = want - got
    print("OK  " if not missing else "FAIL", text[:60], "->", sorted(got), "missing:", sorted(missing) if missing else "")
    ok &= not missing
assert ok
