import ollama
import json
import sys
import re
import math
import os
import subprocess
from .config import OLLAMA_MODEL, OLLAMA_HOST, MIN_CLIP_DURATION, MAX_CLIP_DURATION

def extend_short_clips(clips: list, video_duration: float, target_duration: float = None) -> list:
    """
    Extends clips that are shorter than MIN_CLIP_DURATION by adding time before and after.

    Args:
        clips: List of clip dictionaries with 'start', 'end', 'title', 'reason'
        video_duration: Total duration of the video in seconds
        target_duration: Target minimum duration (defaults to MIN_CLIP_DURATION)

    Returns:
        List of extended clips
    """
    if target_duration is None:
        target_duration = MIN_CLIP_DURATION

    extended_clips = []

    for clip in clips:
        original_start = clip['start']
        original_end = clip['end']
        original_duration = original_end - original_start

        if original_duration >= target_duration:
            # Clip is already long enough
            extended_clips.append(clip)
            print(f"Clip '{clip.get('title', 'Unknown')}' is already {original_duration:.1f}s (>= {target_duration}s)")
        else:
            # Calculate how much time we need to add
            additional_time = target_duration - original_duration

            # Add time evenly before and after
            time_before = additional_time / 2
            time_after = additional_time / 2

            # Calculate new start and end
            new_start = max(0, original_start - time_before)
            new_end = min(video_duration, original_end + time_after)

            # If we hit the start boundary, add more to the end
            if new_start == 0 and (new_end - new_start) < target_duration:
                new_end = min(video_duration, target_duration)

            # If we hit the end boundary, add more to the start
            if new_end == video_duration and (new_end - new_start) < target_duration:
                new_start = max(0, video_duration - target_duration)

            extended_clip = {
                'start': new_start,
                'end': new_end,
                'title': clip.get('title', 'タイトルなし'),
                'reason': clip.get('reason', '興味深い瞬間') + f" ({original_duration:.1f}秒から拡張)"
            }

            extended_clips.append(extended_clip)
            print(f"Extended clip '{clip.get('title', 'Unknown')}' from {original_duration:.1f}s to {new_end - new_start:.1f}s (start: {original_start:.1f}→{new_start:.1f}, end: {original_end:.1f}→{new_end:.1f})")

    return extended_clips

def detect_silence_boundaries(video_path: str, min_silence_len: int = 800, silence_thresh: int = -40) -> list:
    """
    音声ファイルから無音区間を検出して、話の区切り候補を返す
    キャッシュ機能付き：一度検出した結果を保存して再利用

    Args:
        video_path: 動画ファイルのパス
        min_silence_len: 最小無音時間（ミリ秒）
        silence_thresh: 無音と判定する音量閾値（dB）

    Returns:
        無音区間の終了時刻のリスト（秒）
    """
    try:
        # キャッシュファイルのパスを生成
        cache_file = f"{video_path}.silence_cache.json"
        cache_key = f"{min_silence_len}_{silence_thresh}"

        # キャッシュが存在すればそれを使用
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    if cache_key in cache_data:
                        boundaries = cache_data[cache_key]
                        sys.stderr.write(f"[SILENCE_DETECTOR] Using cached silence boundaries ({len(boundaries)} boundaries)\n")
                        sys.stderr.flush()
                        return boundaries
            except Exception as e:
                sys.stderr.write(f"[SILENCE_DETECTOR] Cache read error: {e}, proceeding with detection\n")
                sys.stderr.flush()

        sys.stderr.write(f"[SILENCE_DETECTOR] Detecting silence using ffmpeg (min_len={min_silence_len}ms, thresh={silence_thresh}dB)...\n")
        sys.stderr.flush()

        # Convert ms to seconds for ffmpeg
        duration_sec = min_silence_len / 1000.0

        # Construct ffmpeg command
        # ffmpeg -i input.mp4 -af silencedetect=noise=-40dB:d=0.8 -f null -
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-af', f'silencedetect=noise={silence_thresh}dB:d={duration_sec}',
            '-f', 'null',
            '-'
        ]

        # Run ffmpeg
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        _, stderr = process.communicate()

        # Parse output for silence_end
        boundaries = []
        for line in stderr.split('\n'):
            if 'silence_end' in line:
                # Example: [silencedetect @ ...] silence_end: 125.789 | silence_duration: 2.333
                try:
                    parts = line.split('silence_end: ')
                    if len(parts) > 1:
                        end_time_str = parts[1].split('|')[0].strip()
                        boundaries.append(float(end_time_str))
                except Exception as e:
                    print(f"Error parsing line: {line}, error: {e}")

        sys.stderr.write(f"[SILENCE_DETECTOR] Found {len(boundaries)} silence boundaries\n")
        sys.stderr.flush()

        # キャッシュに保存
        try:
            cache_data = {}
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
            cache_data[cache_key] = boundaries
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
            sys.stderr.write(f"[SILENCE_DETECTOR] Cached silence boundaries to {cache_file}\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[SILENCE_DETECTOR] Cache write error: {e}\n")
            sys.stderr.flush()

        return boundaries
    except Exception as e:
        sys.stderr.write(f"[SILENCE_DETECTOR] Error: {e}\n")
        sys.stderr.flush()
        return []

def detect_sentence_boundaries(segments: list) -> list:
    """
    文字起こしセグメントから文章の区切りを検出

    Args:
        segments: Whisperの文字起こしセグメント

    Returns:
        文章区切りの時刻リスト（秒）
    """
    boundaries = []

    # 句読点や改行で文章の区切りを判定
    sentence_end_patterns = [r'[。！？\n]', r'[.!?]\s', r'\n']

    for seg in segments:
        text = seg.text if hasattr(seg, 'text') else seg['text']
        end_time = seg.end if hasattr(seg, 'end') else seg['end']

        # 文末記号があれば境界候補
        for pattern in sentence_end_patterns:
            if re.search(pattern, text):
                boundaries.append(end_time)
                break

    sys.stderr.write(f"[SENTENCE_DETECTOR] Found {len(boundaries)} sentence boundaries\n")
    sys.stderr.flush()

    return boundaries

def detect_boundaries_hybrid(video_path: str, segments: list, max_clips: int = 5, start_time: float = 0) -> list:
    """
    ハイブリッド方式：無音区間 + 文章区切り + 時間制約を組み合わせて境界を検出

    Args:
        video_path: 動画ファイルのパス
        segments: Whisperの文字起こしセグメント
        max_clips: 目標クリップ数
        start_time: 解析開始時刻（秒）

    Returns:
        境界の時刻リスト（秒）
    """
    sys.stderr.write(f"[HYBRID_DETECTOR] Starting hybrid boundary detection (start_time={start_time}s)...\n")
    sys.stderr.flush()

    # 動画の長さを取得
    if not segments:
        return []

    # start_time以降のセグメントのみをフィルタリング
    if start_time > 0:
        filtered_segments = [
            seg for seg in segments
            if (seg.start if hasattr(seg, 'start') else seg['start']) >= start_time
        ]
        if not filtered_segments:
            sys.stderr.write(f"[HYBRID_DETECTOR] No segments found after start_time={start_time}s\n")
            sys.stderr.flush()
            return []
        segments = filtered_segments
        sys.stderr.write(f"[HYBRID_DETECTOR] Filtered to {len(segments)} segments after start_time={start_time}s\n")
        sys.stderr.flush()

    first_time = segments[0].start if hasattr(segments[0], 'start') else segments[0]['start']
    last_time = segments[-1].end if hasattr(segments[-1], 'end') else segments[-1]['end']

    # Get actual video duration from file (not from segments)
    from .video_processing import get_video_info
    try:
        video_info = get_video_info(video_path)
        actual_video_duration = video_info['duration']
    except Exception as e:
        sys.stderr.write(f"[HYBRID_DETECTOR] Warning: Could not get video duration from file: {e}, using segments\n")
        sys.stderr.flush()
        actual_video_duration = last_time - first_time

    # 1. 無音区間を検出
    # 動画が3時間以上の場合、初回実行ではsilence detectionをスキップ（キャッシュがある場合は使用）
    silence_boundaries = []
    cache_file = f"{video_path}.silence_cache.json"
    if actual_video_duration > 10800:  # 3 hours
        if os.path.exists(cache_file):
            sys.stderr.write(f"[HYBRID_DETECTOR] Long video ({actual_video_duration/3600:.1f}h), checking for cached silence data...\n")
            sys.stderr.flush()
            silence_boundaries = detect_silence_boundaries(video_path)
        else:
            sys.stderr.write(f"[HYBRID_DETECTOR] Skipping silence detection for long video ({actual_video_duration/3600:.1f}h, no cache found)\n")
            sys.stderr.flush()
    else:
        silence_boundaries = detect_silence_boundaries(video_path)

    # 2. 文章区切りを検出
    sentence_boundaries = detect_sentence_boundaries(segments)

    # 3. 両方の境界候補を統合
    all_boundaries = set(silence_boundaries + sentence_boundaries)
    all_boundaries = sorted(list(all_boundaries))

    sys.stderr.write(f"[HYBRID_DETECTOR] Total candidate boundaries: {len(all_boundaries)}\n")
    sys.stderr.flush()

    # 4. 境界をフィルタリング
    # - 最初と最後の境界を追加
    # - 近すぎる境界を統合（MIN_CLIP_DURATION秒以内）
    # - 目標数に合わせて間引き

    if not all_boundaries:
        return []

    filtered_boundaries = [first_time]

    for boundary in all_boundaries:
        # 範囲内かチェック
        if boundary < first_time or boundary > last_time:
            continue

        # 前の境界と十分離れているかチェック
        if boundary - filtered_boundaries[-1] >= MIN_CLIP_DURATION:
            filtered_boundaries.append(boundary)

    # 最後の境界を追加
    if filtered_boundaries[-1] < last_time - MIN_CLIP_DURATION:
        filtered_boundaries.append(last_time)

    # 5. 境界が多すぎる場合は均等に間引き
    target_boundaries = max_clips + 1  # クリップ数=境界数-1
    if len(filtered_boundaries) > target_boundaries:
        # 重要度でソート（無音と文章の両方で検出された境界を優先）
        boundary_scores = []
        for b in filtered_boundaries[1:-1]:  # 最初と最後は除外
            score = 0
            if any(abs(b - sb) < 0.5 for sb in silence_boundaries):
                score += 2  # 無音境界は重要度高
            if any(abs(b - sb) < 0.5 for sb in sentence_boundaries):
                score += 1  # 文章境界
            boundary_scores.append((b, score))

        # スコアでソートして上位を選択
        boundary_scores.sort(key=lambda x: x[1], reverse=True)
        selected = [first_time] + [b for b, s in boundary_scores[:target_boundaries-2]] + [last_time]
        filtered_boundaries = sorted(selected)

    sys.stderr.write(f"[HYBRID_DETECTOR] Final boundaries: {len(filtered_boundaries)}\n")
    sys.stderr.flush()

    # 境界からクリップを作成（区切りと区切りの間がクリップ）
    clips = []
    for i in range(len(filtered_boundaries) - 1):
        start = filtered_boundaries[i]
        end = filtered_boundaries[i + 1]
        duration = end - start

        # 最大時間を超える場合は制限
        if duration > MAX_CLIP_DURATION:
            end = start + MAX_CLIP_DURATION
            duration = MAX_CLIP_DURATION

        # MIN_CLIP_DURATION以上のクリップのみ追加
        if duration >= MIN_CLIP_DURATION:
            clip = {
                'start': start,
                'end': end,
                'title': f'区間 {i+1}',
                'reason': f"{duration:.1f}秒のクリップ（ハイブリッド検出）"
            }
            clips.append(clip)
            sys.stderr.write(f"[HYBRID_DETECTOR] Clip {i+1}: {start:.1f}-{end:.1f} ({duration:.1f}s)\n")
            sys.stderr.flush()

    sys.stderr.write(f"[HYBRID_DETECTOR] Generated {len(clips)} clips from {len(filtered_boundaries)} boundaries\n")
    sys.stderr.flush()

    return clips

def _build_comment_summary(comments: list, window_start: float, window_end: float,
                           bucket_sec: float = 30.0) -> str:
    """
    指定時間帯のコメントを bucket_sec 秒単位でまとめ、
    AIプロンプトに挿入できる文字列を生成する。

    返す形式:
        [120s] (12 comments) w www すごい！ 草草草 やばすぎ ...
        [150s] (5 comments) かわいい ...
    """
    if not comments:
        return ""

    # 対象時間帯でフィルタ
    filtered = [c for c in comments
                if window_start <= c.get('timestamp', -1) < window_end]
    if not filtered:
        return ""

    # バケット単位で集計
    import math
    buckets: dict[int, list[str]] = {}
    for c in filtered:
        ts = c.get('timestamp', 0)
        bucket = int(ts // bucket_sec) * int(bucket_sec)
        buckets.setdefault(bucket, []).append(c.get('text', '').strip())

    lines = []
    for bucket_ts in sorted(buckets.keys()):
        texts = buckets[bucket_ts]
        # 先頭 8 コメントだけ表示（長くなりすぎ防止）
        preview = ' / '.join(texts[:8])
        if len(texts) > 8:
            preview += f' ... (+{len(texts)-8})'
        lines.append(f"[{bucket_ts}s] ({len(texts)} comments) {preview}")

    return '\n'.join(lines)


def _analyze_chunk_with_ai(segments: list, comments: list,
                            first_ts: float, last_ts: float,
                            target_boundaries: int,
                            context: str = '',
                            ollama_host: str = None,
                            ollama_model: str = None) -> list:
    """
    1つの時間チャンクを Ollama で解析して境界リストを返す内部関数。
    """
    # ── 字幕テキスト組み立て ────────────────────────────────────────────────
    transcript_text = ""
    for seg in segments:
        start = seg.get('start') if isinstance(seg, dict) else seg.start
        end   = seg.get('end')   if isinstance(seg, dict) else seg.end
        text  = seg.get('text')  if isinstance(seg, dict) else seg.text
        transcript_text += f"[{start:.1f}-{end:.1f}] {text}\n"

    # ── コメントサマリー組み立て ─────────────────────────────────────────────
    comment_section = ""
    if comments:
        summary = _build_comment_summary(comments, first_ts, last_ts, bucket_sec=30.0)
        if summary:
            comment_section = f"\n\nLive chat comments (30-second buckets):\n{summary}\n"

    has_comments = bool(comment_section)
    context_line = f"\nContext: {context}" if context else ""

    prompt = f"""You are a JSON generator that finds interesting clip boundaries in a Japanese livestream.
{context_line}

Video range: {first_ts:.1f}s - {last_ts:.1f}s
Find EXACTLY {target_boundaries} timestamps where exciting/interesting moments occur.
{"Use BOTH the transcript AND the live chat comments to identify high-energy moments (many comments, laughter 'w'/'草', excitement, reactions)." if has_comments else "Use the transcript to identify topic shifts and interesting moments."}

REQUIRED OUTPUT format (JSON array only, start with [):
[
  {{"timestamp": 50, "description": "moment description"}},
  {{"timestamp": 150, "description": "moment description"}}
]

RULES:
1. Return ONLY a JSON array starting with [ and ending with ]
2. Include EXACTLY {target_boundaries} objects
3. Timestamps MUST be between {first_ts:.1f} and {last_ts:.1f}
4. Spread timestamps across the full range
5. Prefer timestamps where comments are densest / transcript shows excitement{comment_section}

Transcript:
{transcript_text}

JSON array (start with [):"""

    try:
        actual_host = ollama_host if ollama_host else OLLAMA_HOST
        actual_model = ollama_model if ollama_model else OLLAMA_MODEL
        client = ollama.Client(host=actual_host, timeout=90.0)

        best_boundaries: list = []
        best_count = 0

        for attempt in range(3):
            temp = 0.1 if attempt == 0 else (0.3 if attempt == 1 else 0.5)
            try:
                sys.stderr.write(
                    f"[CLIP_DETECTOR] Chunk {first_ts:.0f}-{last_ts:.0f}s, "
                    f"attempt {attempt+1}/3, temp={temp}, "
                    f"comments={'yes' if has_comments else 'no'}\n"
                )
                sys.stderr.flush()

                response = client.chat(
                    model=actual_model,
                    messages=[
                        {
                            'role': 'system',
                            'content': (
                                'You are a strict JSON array generator. '
                                'Your response MUST start with [ and end with ]. '
                                'NEVER return anything except a JSON array.'
                            )
                        },
                        {'role': 'user', 'content': prompt},
                    ],
                    format='json',
                    options={'temperature': temp, 'num_predict': 1500},
                )

                content = response['message']['content']
                parsed = json.loads(content.strip())

                boundaries: list = []
                if isinstance(parsed, list):
                    boundaries = parsed
                elif isinstance(parsed, dict):
                    for key in ('boundaries', 'clips', 'segments', 'data',
                                'results', 'topics', 'moments'):
                        if key in parsed and isinstance(parsed[key], list):
                            boundaries = parsed[key]
                            break
                    else:
                        if 'timestamp' in parsed:
                            boundaries = [parsed]

                if len(boundaries) > best_count:
                    best_count = len(boundaries)
                    best_boundaries = boundaries
                    if best_count >= target_boundaries:
                        break

            except json.JSONDecodeError:
                import re as _re
                m = _re.search(r'\[.*\]', content, _re.DOTALL)
                if m:
                    try:
                        boundaries = json.loads(m.group(0))
                        if len(boundaries) > best_count:
                            best_count = len(boundaries)
                            best_boundaries = boundaries
                    except Exception:
                        pass
            except Exception as e:
                sys.stderr.write(f"[CLIP_DETECTOR] Attempt {attempt+1} error: {e}\n")
                sys.stderr.flush()

        return best_boundaries

    except Exception as e:
        sys.stderr.write(f"[CLIP_DETECTOR] _analyze_chunk_with_ai error: {e}\n")
        sys.stderr.flush()
        return []

def analyze_transcript_with_ai(segments: list, max_clips: int = 5,
                                start_time: float = 0,
                                comments: list = None,
                                context: str = '',
                                ollama_host: str = None,
                                ollama_model: str = None) -> list:
    """
    Analyzes transcript segments using Ollama to identify interesting clips.

    Args:
        segments: 文字起こしセグメント
        max_clips: 最大クリップ数
        start_time: 解析開始時刻（秒）
        comments: ライブチャットコメントのリスト（各要素は {'timestamp': float, 'text': str}）
        context: 配信者・コンテンツ情報の前提文（プロンプトに挿入される）
    """

    CHUNK_MINUTES = 60          # 1チャンクあたりの時間（分）※スペックアップにより拡大
    MAX_SEGS_PER_CHUNK = 500    # 1チャンクに含める最大セグメント数（スペックアップにより拡大）
    comments = comments or []

    # start_time以降のセグメントのみをフィルタリング
    if start_time > 0:
        segments = [
            seg for seg in segments
            if (seg.get('start') if isinstance(seg, dict) else seg.start) >= start_time
        ]
        if not segments:
            print(f"Warning: No segments found after start_time={start_time}s")
            return []
        print(f"Filtered to {len(segments)} segments after start_time={start_time}s")

    if not segments:
        return []

    def _get(seg, key):
        return seg.get(key) if isinstance(seg, dict) else getattr(seg, key)

    first_time_all = _get(segments[0], 'start')
    last_time_all  = _get(segments[-1], 'end')
    total_duration = last_time_all - first_time_all

    # ── チャンク分割 ────────────────────────────────────────────────────────
    chunk_sec = CHUNK_MINUTES * 60
    if total_duration <= chunk_sec:
        # 短い場合は分割なし
        chunks = [(segments, first_time_all, last_time_all)]
        print(f"[AI_ANALYZE] Single chunk: {first_time_all:.0f}s-{last_time_all:.0f}s "
              f"({total_duration/60:.1f}min, comments={len(comments)})")
    else:
        chunks = []
        chunk_start = first_time_all
        while chunk_start < last_time_all:
            chunk_end = min(chunk_start + chunk_sec, last_time_all)
            chunk_segs = [s for s in segments
                          if _get(s, 'start') >= chunk_start and _get(s, 'end') <= chunk_end + 10]
            if chunk_segs:
                chunks.append((chunk_segs, chunk_start, chunk_end))
            chunk_start = chunk_end
        print(f"[AI_ANALYZE] Split into {len(chunks)} chunks "
              f"({CHUNK_MINUTES}min each, total {total_duration/60:.1f}min, comments={len(comments)})")

    # ── 各チャンクの境界数を配分 ─────────────────────────────────────────────
    # 合計でおよそ max_clips*2 個の境界を得る（最小6、最大10/chunk）
    target_total_boundaries = max(6, min(len(chunks) * 10, max_clips * 2 + 2))
    boundaries_per_chunk = max(4, target_total_boundaries // len(chunks))

    # ── チャンクごとにAI解析 ─────────────────────────────────────────────────
    all_raw_boundaries: list = []

    for chunk_idx, (chunk_segs, c_start, c_end) in enumerate(chunks):
        print(f"[AI_ANALYZE] Chunk {chunk_idx+1}/{len(chunks)}: "
              f"{c_start:.0f}s-{c_end:.0f}s ({len(chunk_segs)} segs)")

        # セグメント数が多すぎる場合は時間ベースでサンプリング
        if len(chunk_segs) > MAX_SEGS_PER_CHUNK:
            time_range = c_end - c_start
            sampled: list = []
            for i in range(MAX_SEGS_PER_CHUNK):
                target_t = c_start + (time_range * i / MAX_SEGS_PER_CHUNK)
                closest = min(chunk_segs, key=lambda s: abs(_get(s, 'start') - target_t))
                if not sampled or closest is not sampled[-1]:
                    sampled.append(closest)
            chunk_segs = sampled
            print(f"[AI_ANALYZE]   Sampled to {len(chunk_segs)} segments")

        raw = _analyze_chunk_with_ai(
            segments=chunk_segs,
            comments=comments,
            first_ts=c_start,
            last_ts=c_end,
            target_boundaries=boundaries_per_chunk,
            context=context,
            ollama_host=ollama_host,
            ollama_model=ollama_model
        )
        print(f"[AI_ANALYZE]   Got {len(raw)} raw boundaries from chunk {chunk_idx+1}")
        all_raw_boundaries.extend(raw)

    # ── 全チャンクの境界を正規化 ─────────────────────────────────────────────
    def _normalize_boundary(b) -> dict | None:
        if not isinstance(b, dict):
            return None
        ts = (b.get('timestamp') or b.get('start') or
              b.get('start_time') or b.get('time'))
        if ts is None:
            return None
        desc = (b.get('description') or b.get('topic') or
                b.get('title') or 'トピック境界')
        return {'timestamp': float(ts), 'description': str(desc)}

    boundaries = []
    for b in all_raw_boundaries:
        norm = _normalize_boundary(b)
        if norm and first_time_all <= norm['timestamp'] <= last_time_all:
            boundaries.append(norm)

    boundaries = sorted(boundaries, key=lambda x: x['timestamp'])
    print(f"[AI_ANALYZE] Normalized to {len(boundaries)} valid boundaries "
          f"({first_time_all:.0f}s-{last_time_all:.0f}s)")

    # ── 境界が少ない場合はフォールバック ─────────────────────────────────────
    if len(boundaries) < 2:
        sys.stderr.write(f"[CLIP_DETECTOR] WARNING: Only {len(boundaries)} boundaries, adding fallback.\n")
        needed = max(6, target_total_boundaries) - len(boundaries)
        for i in range(needed):
            t = first_time_all + (last_time_all - first_time_all) * (i + 1) / (needed + 1)
            boundaries.append({'timestamp': t, 'description': f'区間{i+1}'})
        boundaries = sorted(boundaries, key=lambda x: x['timestamp'])
        print(f"[AI_ANALYZE] Added fallback boundaries, total={len(boundaries)}")

    # ── 境界 → クリップ変換 ───────────────────────────────────────────────
    raw_clips = []
    for i in range(len(boundaries) - 1):
        s = boundaries[i]['timestamp']
        e = boundaries[i + 1]['timestamp']
        dur = e - s
        if dur > MAX_CLIP_DURATION:
            e = s + MAX_CLIP_DURATION
            dur = MAX_CLIP_DURATION
        raw_clips.append({
            'start': s, 'end': e,
            'title': boundaries[i + 1].get('description', 'トピック'),
            'duration': dur,
        })

    # ── MIN_CLIP_DURATION 未満は隣と結合 ─────────────────────────────────
    merged_clips = []
    i = 0
    while i < len(raw_clips):
        cur = raw_clips[i].copy()
        while cur['duration'] < MIN_CLIP_DURATION and i + 1 < len(raw_clips):
            nxt = raw_clips[i + 1]
            cur['end'] = nxt['end']
            cur['duration'] = cur['end'] - cur['start']
            if cur['title'] != nxt['title']:
                cur['title'] = f"{cur['title']} → {nxt['title']}"
            i += 1
        if cur['duration'] > MAX_CLIP_DURATION:
            cur['end'] = cur['start'] + MAX_CLIP_DURATION
            cur['duration'] = MAX_CLIP_DURATION
        if cur['duration'] >= MIN_CLIP_DURATION:
            merged_clips.append({
                'start': cur['start'],
                'end': cur['end'],
                'title': cur['title'],
                'reason': f"{cur['duration']:.1f}秒のクリップ",
            })
        i += 1

    print(f"[AI_ANALYZE] Generated {len(merged_clips)} clips from {len(boundaries)} boundaries")
    return merged_clips

def evaluate_clip_quality(vtt_path: str, start_time: float, end_time: float, ollama_host: str = None, ollama_model: str = None) -> dict:
    """
    Evaluates the quality/interestingness of a clip using AI.
    Returns a score (1-5 stars) and reasoning.

    Args:
        vtt_path: Path to the VTT subtitle file
        start_time: Clip start time in seconds
        end_time: Clip end time in seconds

    Returns:
        dict with 'score' (int 1-5) and 'reason' (str)
    """
    try:
        # Parse VTT to extract text for this time range
        with open(vtt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        clip_text = ""
        current_start = 0
        current_end = 0

        for i, line in enumerate(lines):
            if "-->" in line:
                times = line.strip().split(" --> ")

                def parse_time(t):
                    parts = t.split(":")
                    seconds = float(parts[-1])
                    if len(parts) > 1:
                        seconds += int(parts[-2]) * 60
                    if len(parts) > 2:
                        seconds += int(parts[-3]) * 3600
                    return seconds

                current_start = parse_time(times[0])
                current_end = parse_time(times[1])

                # Check if this segment is within the clip range
                if current_start >= start_time and current_end <= end_time:
                    # Get the text line (next non-empty line)
                    if i + 1 < len(lines):
                        text_line = lines[i + 1].strip()
                        if text_line and not text_line.isdigit() and "WEBVTT" not in text_line:
                            clip_text += text_line + " "

        if not clip_text.strip():
            return {"score": 3, "reason": "字幕テキストが見つかりませんでした"}

        sys.stderr.write(f"[CLIP_EVALUATOR] Evaluating clip {start_time:.1f}-{end_time:.1f}\n")
        sys.stderr.write(f"[CLIP_EVALUATOR] Clip text length: {len(clip_text)} chars\n")
        sys.stderr.flush()

        # Prompt for AI evaluation
        prompt = f"""あなたはJSON専用のAPIです。必ず有効なJSONのみで応答してください。

この動画クリップの面白さを評価して、スコア（1-5つ星）を推奨してください。

重要: 応答はJSONオブジェクトのみにしてください。説明やテキストは不要、JSONのみです。

応答フォーマットの例（これが応答全体の形式です）:
{{"score": 4, "reason": "面白い会話で視聴者を引き込む内容"}}

スコアリング基準:
⭐️ 1つ星: つまらない、繰り返しで価値なし
⭐️⭐️ 2つ星: やや興味深いがインパクト不足
⭐️⭐️⭐️ 3つ星: まあまあの内容、見る価値あり
⭐️⭐️⭐️⭐️ 4つ星: とても面白い、魅力的な内容
⭐️⭐️⭐️⭐️⭐️ 5つ星: 傑出した、必見の瞬間

クリップ時間: {end_time - start_time:.1f}秒
クリップの文字起こし:
{clip_text}

スコア（1-5）とreason（理由を日本語で）を含むJSONオブジェクト（JSONのみで応答、他のテキストは含めない）:"""

        actual_host = ollama_host if ollama_host else OLLAMA_HOST
        actual_model = ollama_model if ollama_model else OLLAMA_MODEL
        client = ollama.Client(host=actual_host, timeout=60.0)
        response = client.chat(model=actual_model, messages=[
            {
                'role': 'user',
                'content': prompt,
            },
        ], format='json', options={'temperature': 0.3})

        # Extract content from response
        content = response['message']['content']
        sys.stderr.write(f"[CLIP_EVALUATOR] Response: {content[:200]}\n")
        sys.stderr.flush()

        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)

        result = json.loads(content.strip())

        # Validate score is 1-5
        if 'score' in result and isinstance(result['score'], (int, float)):
            result['score'] = max(1, min(5, int(result['score'])))
        else:
            result['score'] = 3

        if 'reason' not in result:
            result['reason'] = "評価理由が取得できませんでした"

        sys.stderr.write(f"[CLIP_EVALUATOR] Score: {result['score']}/5 - {result['reason']}\n")
        sys.stderr.flush()

        return result

    except Exception as e:
        sys.stderr.write(f"[CLIP_EVALUATOR] Error: {e}\n")
        sys.stderr.flush()
        return {"score": 3, "reason": f"評価エラー: {str(e)}"}

    # TODO: Implement VTT parsing if needed.
    # For now, we will rely on the main flow passing segments or re-reading them.
    pass

def count_comments_in_clips(clips: list, comments_path: str) -> list:
    """
    Counts comments within the time range of each clip.
    
    Args:
        clips: List of clip dictionaries
        comments_path: Path to the .info.json file containing comments
        
    Returns:
        List of clips with 'comment_count' field added
    """
    try:
        if not os.path.exists(comments_path):
            print(f"Comments file not found: {comments_path}")
            return clips
            
        print(f"Loading comments from {comments_path}...")
        
        comment_times = []
        
        # Check if it's a live chat file (NDJSON)
        if comments_path.endswith('.live_chat.json'):
            print("Parsing live chat data (NDJSON)...")
            with open(comments_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        # Extract videoOffsetTimeMsec
                        # Structure: replayChatItemAction -> videoOffsetTimeMsec
                        if 'replayChatItemAction' in data:
                            action = data['replayChatItemAction']
                            if 'videoOffsetTimeMsec' in action:
                                msec = int(action['videoOffsetTimeMsec'])
                                comment_times.append(msec / 1000.0)
                    except Exception as e:
                        print(f"Error parsing line: {e}")
                        continue
                        
            print(f"Parsed {len(comment_times)} timestamps from live chat file.")
            if comment_times:
                print(f"Comment time range: {min(comment_times):.1f}s to {max(comment_times):.1f}s")
                        
        else:
            # Standard info.json format
            print("Parsing standard info.json...")
            with open(comments_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract comments
            comments = []
            if 'comments' in data:
                comments = data['comments']
            else:
                print("No 'comments' field in JSON data")
                return clips
                
            print(f"Found {len(comments)} comments. Counting per clip...")
            
            for c in comments:
                t = None
                
                # 1. Check for explicit offset (Live Chat)
                if 'offset_seconds' in c:
                    t = float(c['offset_seconds'])
                
                # 2. Check for timestamps in text
                if t is None and 'text' in c:
                    text = c['text']
                    # Search for mm:ss or h:mm:ss pattern
                    match = re.search(r'(?:(\d+):)?(\d+):(\d+)', text)
                    if match:
                        # Found a timestamp in comment
                        groups = match.groups()
                        seconds = int(groups[2])
                        minutes = int(groups[1])
                        hours = int(groups[0]) if groups[0] else 0
                        t = hours * 3600 + minutes * 60 + seconds
                
                if t is not None:
                    comment_times.append(t)
                
        print(f"Extracted {len(comment_times)} time-synced comments/timestamps")
        
        # Count for each clip
        for clip in clips:
            start = clip['start']
            end = clip['end']
            duration = end - start
            count = sum(1 for t in comment_times if start <= t <= end)
            clip['comment_count'] = count
            
            # Calculate comments per minute
            if duration > 0:
                cpm = (count / duration) * 60
                clip['comments_per_minute'] = round(cpm, 1)
            else:
                clip['comments_per_minute'] = 0
                
            print(f"Clip '{clip['title']}' ({start:.1f}-{end:.1f}): {count} comments ({clip['comments_per_minute']}/min)")
            
        return clips
        
    except Exception as e:
        print(f"Error counting comments: {e}")
        import traceback
        traceback.print_exc()
        return clips

def detect_emoji_density_clips(comments_path: str, video_duration: float, category: str = "kusa", custom_patterns: list = None, clip_duration: int = 60, start_time: float = 0) -> list:
    """
    Detects clips based on specific emoji/pattern density in comments.
    
    Args:
        comments_path: Path to comments file
        video_duration: Video duration
        category: "kusa", "kawaii", etc.
        custom_patterns: List of custom stamp shortcuts to count
        clip_duration: Window size
    """
    try:
        if not os.path.exists(comments_path):
            return []

        print(f"[STAMP_DETECTOR] Analyzing {category} intensity from {comments_path}...")
        events = []
        
        # Default patterns based on category
        patterns = []
        regex_patterns = []
        
        if category == "kusa":
            patterns = [':*kusa*:', ':kusa:', '草', '草生える', '草生えた', '大草原', '草不可避', 'くさ', 'クサ', 'ｸｻ']
            regex_patterns = [r'[wWｗＷ]{3,}']
        elif category == "kawaii":
            patterns = ['かわいい', 'カワイイ', '可愛い', 'kawaii', 'Kawaii', 'てぇてぇ', '助かる', 'たすかる', '天使']
        
        if custom_patterns:
            # shortcuts might be provided without colons in config, but chat has colons
            for p in custom_patterns:
                patterns.append(p)
                if not p.startswith(':'):
                    patterns.append(f":{p}:")

        # Parsing logic (generalized)
        if comments_path.endswith('.live_chat.json'):
            with open(comments_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        if 'replayChatItemAction' not in data: continue
                        action = data['replayChatItemAction']
                        if 'videoOffsetTimeMsec' not in action: continue
                        timestamp = int(action['videoOffsetTimeMsec']) / 1000.0
                        
                        count = 0
                        actions = action.get('actions', [])
                        for act in actions:
                            if 'addChatItemAction' in act:
                                item = act['addChatItemAction'].get('item', {})
                                if 'liveChatTextMessageRenderer' in item:
                                    message_data = item['liveChatTextMessageRenderer'].get('message', {})
                                    runs = message_data.get('runs', [])
                                    for run in runs:
                                        if 'text' in run:
                                            text = run['text']
                                            for p in patterns:
                                                count += text.count(p)
                                            for rp in regex_patterns:
                                                import re
                                                count += len(re.findall(rp, text))
                                        if 'emoji' in run:
                                            emoji = run['emoji']
                                            shortcuts = emoji.get('shortcuts', [])
                                            search_terms = emoji.get('searchTerms', [])
                                            
                                            found = False
                                            for s in shortcuts:
                                                if s in patterns: found = True; break
                                                if category == "kusa" and 'kusa' in s.lower(): found = True; break
                                                if category == "kawaii" and any(k in s.lower() for k in ['kawai', 'angle', 'cute']): found = True; break
                                            
                                            if not found:
                                                for t in search_terms:
                                                    if t in patterns: found = True; break
                                                    if category == "kusa" and 'kusa' in t.lower(): found = True; break
                                                    if category == "kawaii" and any(k in t.lower() for k in ['kawai', 'angle', 'cute']): found = True; break
                                            
                                            if found: count += 1
                                            
                        if count > 0:
                            if timestamp >= start_time:
                                events.append((timestamp, count))
                    except: continue
        else:
            # info.json fallback
            with open(comments_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for c in data.get('comments', []):
                timestamp = c.get('offset_seconds')
                if timestamp is None: continue
                text = c.get('text', '')
                count = 0
                for p in patterns:
                    count += text.count(p)
                for rp in regex_patterns:
                    import re
                    count += len(re.findall(rp, text))
                if count > 0:
                    if timestamp >= start_time:
                        events.append((float(timestamp), count))

        if not events: return []

        # Find peak windows
        window_stats = {}
        for timestamp, count in events:
            window_start = int(timestamp // clip_duration) * clip_duration
            window_stats[window_start] = window_stats.get(window_start, 0) + count

        sorted_windows = sorted(window_stats.items(), key=lambda x: x[1], reverse=True)
        top_windows = sorted_windows[:10]
        top_windows.sort(key=lambda x: x[0])

        clips = []
        display_category = category.capitalize() if category else "スタンプ"
        reason_label = category if category else "指定スタンプ"
        for i, (start_time, count) in enumerate(top_windows):
            clips.append({
                'start': start_time,
                'end': min(video_duration, start_time + clip_duration),
                'title': f'{display_category}ハイライト {i+1}',
                'reason': f'{reason_label}盛り上がり回数: {count}回',
                'stars': min(5, max(1, int(count / 10))) # Simple star heuristic
            })
        return clips
    except Exception as e:
        print(f"Error in detect_emoji_density_clips: {e}")
        return []

def detect_kusa_emoji_clips(comments_path: str, video_duration: float, clip_duration: int = 60) -> list:
    """
    Legacy wrapper for kusa detection.
    """
    return detect_emoji_density_clips(comments_path, video_duration, "kusa", None, clip_duration)



def detect_comment_density_clips(comments_path: str, video_duration: float, clip_duration: int = 60, start_time: float = 0) -> list:
    """
    Detects clips based on comment density (total number of comments per minute).
    Analyzes 1-minute windows and returns top 10 clips with highest comment count.

    Args:
        comments_path: Path to the live chat JSON file
        video_duration: Total video duration in seconds
        clip_duration: Duration of each clip in seconds (default: 60s = 1 minute)

    Returns:
        List of clip dictionaries sorted by comment count (descending)
    """
    try:
        if not os.path.exists(comments_path):
            print(f"[COMMENT_DENSITY] Comments file not found: {comments_path}")
            return []

        comment_events = []  # List of timestamps

        # Parse live chat (NDJSON)
        if comments_path.endswith('.live_chat.json'):
            print("[COMMENT_DENSITY] Parsing live chat data (NDJSON)...")
            with open(comments_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f):
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)

                        # Extract timestamp
                        if 'replayChatItemAction' in data:
                            action = data['replayChatItemAction']

                            # Get timestamp
                            if 'videoOffsetTimeMsec' not in action:
                                continue
                            timestamp = int(action['videoOffsetTimeMsec']) / 1000.0

                            # Check if it's an actual chat message (not system messages)
                            actions = action.get('actions', [])
                            for act in actions:
                                if 'addChatItemAction' in act:
                                    item = act['addChatItemAction'].get('item', {})

                                    # Count text messages and paid messages
                                    if 'liveChatTextMessageRenderer' in item or \
                                       'liveChatPaidMessageRenderer' in item or \
                                       'liveChatPaidStickerRenderer' in item or \
                                       'liveChatMembershipItemRenderer' in item:
                                        if timestamp >= start_time:
                                            comment_events.append(timestamp)
                                        break  # Only count once per action

                    except Exception as e:
                        if line_num < 10:  # Only log first 10 errors
                            print(f"[COMMENT_DENSITY] Error parsing line {line_num}: {e}")
                        continue

            print(f"[COMMENT_DENSITY] Found {len(comment_events)} comments")

        else:
            # Parse info.json if it exists
            print("[COMMENT_DENSITY] Parsing info.json...")
            with open(comments_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            comments = data.get('comments', [])
            print(f"[COMMENT_DENSITY] Found {len(comments)} comments")

            for c in comments:
                # Get timestamp
                timestamp = None
                if 'offset_seconds' in c:
                    timestamp = float(c['offset_seconds'])

                if timestamp is not None:
                    if timestamp >= start_time:
                        comment_events.append(timestamp)

        if not comment_events:
            print("[COMMENT_DENSITY] No comments found")
            return []

        print(f"[COMMENT_DENSITY] Total comments: {len(comment_events)}")

        # Group by time windows (1 minute intervals)
        window_stats = {}  # {start_time: comment_count}

        for timestamp in comment_events:
            # Round down to nearest minute
            window_start = int(timestamp // clip_duration) * clip_duration

            if window_start not in window_stats:
                window_stats[window_start] = 0
            window_stats[window_start] += 1

        # Create clips from windows
        clips = []
        for start_time, comment_count in window_stats.items():
            end_time = min(start_time + clip_duration, video_duration)

            # Skip clips that are too short
            if end_time - start_time < 10:
                continue

            clips.append({
                'start': start_time,
                'end': end_time,
                'comment_count': comment_count,
                'comments_per_minute': comment_count / ((end_time - start_time) / 60.0),
                'title': f'コメント {comment_count}件 ({start_time//60:.0f}:{start_time%60:02.0f})',
                'reason': f'この1分間に{comment_count}件のコメントがありました（盛り上がっている箇所）'
            })

        # Sort by comment count (descending) and take top 10
        clips.sort(key=lambda x: x['comment_count'], reverse=True)
        top_clips = clips[:10]

        print(f"[COMMENT_DENSITY] Top 10 clips by comment density:")
        for i, clip in enumerate(top_clips, 1):
            print(f"  {i}. {clip['start']:.0f}-{clip['end']:.0f}s: {clip['comment_count']} comments ({clip['comments_per_minute']:.1f}/min)")

        return top_clips

    except Exception as e:
        print(f"[COMMENT_DENSITY] Error: {e}")
        import traceback
        traceback.print_exc()
        return []
