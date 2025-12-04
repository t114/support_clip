import ollama
import json
import sys
import re
from pydub import AudioSegment
from pydub.silence import detect_silence
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

    Args:
        video_path: 動画ファイルのパス
        min_silence_len: 最小無音時間（ミリ秒）
        silence_thresh: 無音と判定する音量閾値（dB）

    Returns:
        無音区間の終了時刻のリスト（秒）
    """
    try:
        sys.stderr.write(f"[SILENCE_DETECTOR] Loading audio from {video_path}...\n")
        sys.stderr.flush()

        # 音声を読み込む
        audio = AudioSegment.from_file(video_path)

        sys.stderr.write(f"[SILENCE_DETECTOR] Detecting silence (min_len={min_silence_len}ms, thresh={silence_thresh}dB)...\n")
        sys.stderr.flush()

        # 無音区間を検出
        silence_ranges = detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)

        # 無音区間の終了時刻を境界とする（秒に変換）
        boundaries = []
        for start_ms, end_ms in silence_ranges:
            # 無音区間の終わり = 次の話の始まり
            boundary_time = end_ms / 1000.0
            boundaries.append(boundary_time)

        sys.stderr.write(f"[SILENCE_DETECTOR] Found {len(boundaries)} silence boundaries\n")
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
    video_duration = last_time - first_time

    # 1. 無音区間を検出
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

def analyze_transcript_with_ai(segments: list, max_clips: int = 5, start_time: float = 0) -> list:
    """
    Analyzes transcript segments using Ollama to identify interesting clips.
    
    Args:
        segments: 文字起こしセグメント
        max_clips: 最大クリップ数
        start_time: 解析開始時刻（秒）
    """

    # start_time以降のセグメントのみをフィルタリング
    if start_time > 0:
        filtered_segments = [
            seg for seg in segments
            if (seg.start if hasattr(seg, 'start') else seg['start']) >= start_time
        ]
        
        if not filtered_segments:
            print(f"Warning: No segments found after start_time={start_time}s")
            return []
        
        segments = filtered_segments
        print(f"Filtered to {len(segments)} segments after start_time={start_time}s")

    # If transcript chunk is still too long, sample segments to stay within context limits
    # Ollama llama3.2 has a 4096 token context limit
    MAX_SEGMENTS = 200  # Match CHUNK_SIZE to preserve full context for longer clips

    if len(segments) > MAX_SEGMENTS:
        # Sample segments evenly BASED ON TIME, not just index
        # This ensures we get segments from beginning, middle, and end
        first_time = segments[0].start if hasattr(segments[0], 'start') else segments[0]['start']
        last_time = segments[-1].end if hasattr(segments[-1], 'end') else segments[-1]['end']
        time_range = last_time - first_time

        sampled_segments = []
        for i in range(MAX_SEGMENTS):
            # Calculate target time for this sample
            target_time = first_time + (time_range * i / MAX_SEGMENTS)

            # Find segment closest to target time
            closest_seg = min(segments, key=lambda s: abs(
                (s.start if hasattr(s, 'start') else s['start']) - target_time
            ))

            # Avoid duplicates
            if not sampled_segments or closest_seg != sampled_segments[-1]:
                sampled_segments.append(closest_seg)

        print(f"Chunk too long ({len(segments)} segments). Time-based sampling: {len(sampled_segments)} segments from {first_time:.1f}s to {last_time:.1f}s")
    else:
        sampled_segments = segments
        print(f"Processing {len(segments)} segments")

    # Prepare transcript text for the LLM
    transcript_text = ""
    first_timestamp = None
    last_timestamp = None

    for seg in sampled_segments:
        # seg is expected to be a dict or object with start, end, text
        # faster-whisper segments are objects
        start = seg.start if hasattr(seg, 'start') else seg['start']
        end = seg.end if hasattr(seg, 'end') else seg['end']
        text = seg.text if hasattr(seg, 'text') else seg['text']

        if first_timestamp is None:
            first_timestamp = start
        last_timestamp = end

        transcript_text += f"[{start:.2f}-{end:.2f}] {text}\n"

    # Calculate video duration from transcript
    video_duration = last_timestamp if last_timestamp else 0

    # Calculate target number of boundaries (話の区切り)
    # Aim for 6-10 boundaries to create meaningful clips
    target_boundaries = max(6, min(10, max_clips * 2))

    prompt = f"""You are a JSON generator. Find {target_boundaries} topic boundaries where conversations shift or new topics begin.

Video: {first_timestamp:.1f}s - {last_timestamp:.1f}s (spread boundaries evenly)

REQUIRED OUTPUT - Start your response with [ :
[
  {{"timestamp": 50, "description": "topic 1"}},
  {{"timestamp": 150, "description": "topic 2"}},
  {{"timestamp": 300, "description": "topic 3"}},
  {{"timestamp": 500, "description": "topic 4"}},
  {{"timestamp": 700, "description": "topic 5"}},
  {{"timestamp": 850, "description": "topic 6"}}
]

RULES:
1. MUST be a JSON array starting with [ and ending with ]
2. MUST contain EXACTLY {target_boundaries} objects
3. NEVER return a single object like {{"timestamp":...}}
4. Each object format: {{"timestamp": number, "description": "text"}}
5. Timestamps MUST spread from {first_timestamp:.1f} to {last_timestamp:.1f}

Transcript:
{transcript_text}

Your JSON array (start with [):"""

    try:
        # Try multiple times with different temperatures to get best result
        max_retries = 3
        best_boundaries = []
        best_count = 0

        for attempt in range(max_retries):
            try:
                # Use different temperatures for diversity
                temp = 0.1 if attempt == 0 else (0.3 if attempt == 1 else 0.5)

                sys.stderr.write(f"[CLIP_DETECTOR] Sending prompt to Ollama (model: {OLLAMA_MODEL}, attempt {attempt + 1}/{max_retries}, temp={temp})...\n")
                sys.stderr.write(f"[CLIP_DETECTOR] Transcript length: {len(transcript_text)} chars, {len(sampled_segments)} segments\n")
                sys.stderr.flush()

                client = ollama.Client(host=OLLAMA_HOST)
                response = client.chat(
                    model=OLLAMA_MODEL,
                    messages=[
                        {
                            'role': 'system',
                            'content': 'You are a strict JSON array generator. Your response MUST start with [ and end with ]. NEVER return a single object {}. NEVER return anything except a JSON array. No explanations, no text, ONLY the array.'
                        },
                        {
                            'role': 'user',
                            'content': prompt,
                        }
                    ],
                    format='json',  # Force JSON output
                    options={
                        'temperature': temp,
                        'num_predict': 1000,  # Allow enough tokens for array
                    }
                )

                sys.stderr.write(f"[CLIP_DETECTOR] Got response from Ollama (attempt {attempt + 1})\n")
                content = response['message']['content']
                sys.stderr.write(f"[CLIP_DETECTOR] Response content length: {len(content)} chars\n")
                sys.stderr.flush()

                # Try to parse JSON for this attempt
                try:
                    # With format='json', content should be valid JSON directly
                    parsed = json.loads(content.strip())
                    boundaries = []

                    # If it's a dict, try to extract the array from common keys
                    if isinstance(parsed, dict):
                        # Try common keys that might contain the boundaries array
                        for key in ['boundaries', 'clips', 'segments', 'data', 'results', 'bounds', 'border', 'topics']:
                            if key in parsed and isinstance(parsed[key], list):
                                boundaries = parsed[key]
                                sys.stderr.write(f"[CLIP_DETECTOR] Found array in key '{key}' with {len(boundaries)} items\n")
                                sys.stderr.flush()
                                break
                        else:
                            # Check if it's a single boundary object
                            if ('timestamp' in parsed and not isinstance(parsed.get('timestamp'), list)) or 'start' in parsed:
                                boundaries = [parsed]
                                sys.stderr.write(f"[CLIP_DETECTOR] Single object, wrapping in array\n")
                                sys.stderr.flush()
                    elif isinstance(parsed, list):
                        boundaries = parsed
                        sys.stderr.write(f"[CLIP_DETECTOR] Got JSON array with {len(boundaries)} boundaries\n")
                        sys.stderr.flush()

                    # Update best_boundaries if this attempt is better
                    if len(boundaries) > best_count:
                        best_count = len(boundaries)
                        best_boundaries = boundaries
                        sys.stderr.write(f"[CLIP_DETECTOR] New best: {best_count} boundaries\n")
                        sys.stderr.flush()

                        # If we got enough boundaries, we can stop early
                        if best_count >= target_boundaries:
                            sys.stderr.write(f"[CLIP_DETECTOR] Got target {target_boundaries} boundaries, stopping early\n")
                            sys.stderr.flush()
                            break

                except (json.JSONDecodeError, ValueError) as e:
                    # Fallback: try to extract JSON array
                    sys.stderr.write(f"[CLIP_DETECTOR] Parse failed for attempt {attempt + 1}: {e}\n")
                    import re
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        try:
                            boundaries = json.loads(json_match.group(0).strip())
                            if len(boundaries) > best_count:
                                best_count = len(boundaries)
                                best_boundaries = boundaries
                                sys.stderr.write(f"[CLIP_DETECTOR] Fallback success, new best: {best_count}\n")
                                sys.stderr.flush()
                        except:
                            pass
                    sys.stderr.flush()

            except Exception as e:
                sys.stderr.write(f"[CLIP_DETECTOR] Attempt {attempt + 1} failed: {e}\n")
                sys.stderr.flush()
                continue

        # Use the best boundaries found across all attempts
        boundaries = best_boundaries
        print(f"AI identified {len(boundaries)} topic boundaries (best of {max_retries} attempts)")

        # Normalize boundaries to have 'timestamp' and 'description' fields
        normalized_boundaries = []
        for b in boundaries:
            # Extract timestamp from various possible formats
            timestamp = None
            description = ""

            if isinstance(b, dict):
                # Try different timestamp field names
                if 'timestamp' in b and not isinstance(b['timestamp'], list):
                    timestamp = b['timestamp']
                elif 'start' in b:
                    timestamp = b['start']
                elif 'start_time' in b:
                    timestamp = b['start_time']
                elif 'time' in b:
                    timestamp = b['time']

                # Try different description field names
                if 'description' in b:
                    description = b['description']
                elif 'topic' in b:
                    description = b['topic']
                elif 'title' in b:
                    description = b['title']

            # Only add if we have a valid timestamp
            if timestamp is not None:
                normalized_boundaries.append({
                    'timestamp': float(timestamp),
                    'description': str(description) if description else "トピック境界"
                })
            else:
                sys.stderr.write(f"[CLIP_DETECTOR] Skipping boundary with no valid timestamp: {b}\n")
                sys.stderr.flush()

        boundaries = normalized_boundaries
        print(f"Normalized to {len(boundaries)} valid boundaries")

        # Need at least 2 boundaries to create clips
        if len(boundaries) < 2:
            sys.stderr.write(f"[CLIP_DETECTOR] WARNING: Only {len(boundaries)} boundaries found, need at least 2. Adding fallback boundaries.\n")
            sys.stderr.flush()

            # Add boundaries at regular intervals
            num_needed = max(target_boundaries, 6) - len(boundaries)
            for i in range(num_needed):
                fallback_time = first_timestamp + (last_timestamp - first_timestamp) * (i + 1) / (num_needed + 1)
                boundaries.append({
                    'timestamp': fallback_time,
                    'description': f"区間 {i+1}"
                })
            print(f"Added {num_needed} fallback boundaries, total now: {len(boundaries)}")

        # Sort boundaries by timestamp
        boundaries = sorted(boundaries, key=lambda x: x.get('timestamp', 0))

        # Validate that boundaries are distributed across the video
        if len(boundaries) > 0:
            boundary_times = [b.get('timestamp', 0) for b in boundaries]
            min_boundary = min(boundary_times)
            max_boundary = max(boundary_times)
            time_span = max_boundary - min_boundary
            total_span = last_timestamp - first_timestamp

            print(f"Boundary distribution: {min_boundary:.1f}s to {max_boundary:.1f}s (span: {time_span:.1f}s / {total_span:.1f}s = {time_span/total_span*100:.1f}%)")

            # Divide video into thirds for distribution check
            third = total_span / 3
            range1_end = first_timestamp + third
            range2_end = first_timestamp + (2 * third)

            # Count boundaries in each third
            range1_count = sum(1 for t in boundary_times if first_timestamp <= t < range1_end)
            range2_count = sum(1 for t in boundary_times if range1_end <= t < range2_end)
            range3_count = sum(1 for t in boundary_times if range2_end <= t <= last_timestamp)

            print(f"Distribution by range: Range1={range1_count}, Range2={range2_count}, Range3={range3_count}")

            # Warn if boundaries are too clustered
            if time_span < total_span * 0.3:
                print(f"WARNING: Boundaries are clustered in only {time_span/total_span*100:.1f}% of the video time range!")
            if range1_count > len(boundaries) * 0.7:
                print(f"WARNING: {range1_count}/{len(boundaries)} boundaries are in the first third of the video!")
            if range3_count == 0 and total_span > 300:
                print(f"WARNING: No boundaries detected in the last third of the video!")

        # Create clips from boundaries (区切りと区切りの間をクリップにする)
        clips = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]['timestamp']
            end = boundaries[i + 1]['timestamp']
            duration = end - start

            # 最大時間を超える場合は制限
            if duration > MAX_CLIP_DURATION:
                end = start + MAX_CLIP_DURATION
                duration = MAX_CLIP_DURATION

            clip = {
                'start': start,
                'end': end,
                'title': boundaries[i + 1].get('description', 'トピック'),
                'duration': duration
            }
            clips.append(clip)
            print(f"Initial clip {i+1}: {start:.1f}-{end:.1f} ({duration:.1f}s) - {clip['title']}")

        # 10秒未満のクリップを隣接するクリップと結合
        merged_clips = []
        i = 0
        while i < len(clips):
            current_clip = clips[i].copy()

            # 10秒未満の場合、次のクリップと結合
            while current_clip['duration'] < MIN_CLIP_DURATION and i + 1 < len(clips):
                next_clip = clips[i + 1]
                current_clip['end'] = next_clip['end']
                current_clip['duration'] = current_clip['end'] - current_clip['start']

                # タイトルを結合
                if current_clip['title'] != next_clip['title']:
                    current_clip['title'] = f"{current_clip['title']} → {next_clip['title']}"

                i += 1
                print(f"Merged with next clip: now {current_clip['start']:.1f}-{current_clip['end']:.1f} ({current_clip['duration']:.1f}s)")

            # 最大時間を超える場合は制限
            if current_clip['duration'] > MAX_CLIP_DURATION:
                current_clip['end'] = current_clip['start'] + MAX_CLIP_DURATION
                current_clip['duration'] = MAX_CLIP_DURATION
                print(f"Limited to MAX_CLIP_DURATION: {current_clip['start']:.1f}-{current_clip['end']:.1f} ({current_clip['duration']:.1f}s)")

            # 10秒以上のクリップのみ追加
            if current_clip['duration'] >= MIN_CLIP_DURATION:
                merged_clips.append({
                    'start': current_clip['start'],
                    'end': current_clip['end'],
                    'title': current_clip['title'],
                    'reason': f"{current_clip['duration']:.1f}秒のクリップ"
                })
                print(f"Added clip: {current_clip['start']:.1f}-{current_clip['end']:.1f} ({current_clip['duration']:.1f}s)")
            else:
                print(f"Skipped short clip: {current_clip['start']:.1f}-{current_clip['end']:.1f} ({current_clip['duration']:.1f}s)")

            i += 1

        print(f"Generated {len(merged_clips)} clips from {len(boundaries)} boundaries")
        return merged_clips
    except Exception as e:
        print(f"Error analyzing transcript with AI: {e}")
        import traceback
        traceback.print_exc()
        return []

def evaluate_clip_quality(vtt_path: str, start_time: float, end_time: float) -> dict:
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

        client = ollama.Client(host=OLLAMA_HOST)
        response = client.chat(model=OLLAMA_MODEL, messages=[
            {'role': 'user', 'content': prompt}
        ])

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

def detect_clips(vtt_path: str, max_clips: int = 5) -> list:
    """
    Parses VTT and runs AI analysis.
    This is a helper if we only have the VTT file.
    For now, we might assume we have the segments from the transcription process directly,
    but parsing VTT is good for re-analysis.
    """
    # TODO: Implement VTT parsing if needed.
    # For now, we will rely on the main flow passing segments or re-reading them.
    pass
