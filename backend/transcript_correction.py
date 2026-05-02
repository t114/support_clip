import sys
import json

def remove_repeated_segments(segments: list, similarity_threshold: float = 0.85) -> list:
    """
    連続する重複・類似セグメントをルールベースで除去する。
    Whisperが同じフレーズを繰り返し出力する問題を修正。

    処理の流れ:
        1. 空・空白セグメントを除去（空セグメントがdedup連鎖を切る問題を解消）
        2. セグメント内繰り返しフレーズを修正
        3. ウィンドウ8のdedup（直近8セグメントと比較）

    Args:
        segments: セグメントのリスト
        similarity_threshold: 類似度がこの値以上なら重複とみなす (0〜1)

    Returns:
        重複除去済みセグメントのリスト
    """
    import re

    WINDOW_SIZE = 8  # 直近何個のセグメントを重複チェック対象にするか

    def normalize(text: str) -> str:
        """比較用に正規化（空白・句読点・記号除去、小文字化）"""
        text = re.sub(r'[\\s　、。，．！？!?,.*★☆【】「」『』（）()]', '', text)
        return text.lower()

    def jaccard(a: str, b: str) -> float:
        """簡易文字レベルのJaccard類似度"""
        na, nb = normalize(a), normalize(b)
        if not na and not nb:
            return 1.0
        if not na or not nb:
            return 0.0
        set_a, set_b = set(na), set(nb)
        return len(set_a & set_b) / len(set_a | set_b)

    def remove_intra_repetition(text: str) -> str:
        """
        セグメント内の繰り返しフレーズを除去する。
        例:
          "そうですねそうですねそうですね" → "そうですね"
          "ありがとう ありがとう ありがとう" → "ありがとう"
          "渡め渡め渡め渡め渡め渡め渡め渡め渡め渡め渡め渡" → "渡め"
        """
        if not text:
            return text

        # スペース区切りの単語レベル繰り返し（最低3回分）
        words = text.split()
        if len(words) >= 4:
            half = len(words) // 2
            for rep_len in range(1, half + 1):
                pattern = words[:rep_len]
                chunks = [words[i:i+rep_len] for i in range(0, len(words), rep_len)]
                # 各chunkがpatternの先頭と一致し、3回以上繰り返すなら除去
                if (len(chunks) >= 3 and
                        all(c == pattern[:len(c)] for c in chunks)):
                    return ' '.join(pattern)

        # 文字列レベルの繰り返し（スペースなし日本語向け）
        n = len(text)
        for rep_len in range(2, n // 2 + 1):
            chunk = text[:rep_len]
            # 完全繰り返し
            if n % rep_len == 0 and chunk * (n // rep_len) == text:
                return chunk
            # 端数ありの繰り返し（例: "渡め" × 11 + "渡"）
            reps = n // rep_len
            if reps >= 3 and text.startswith(chunk * reps):
                return chunk

        return text

    if not segments:
        return segments

    # ── Step 1: 空・空白のみのセグメントを除去 ──────────────────────────────
    non_empty = []
    for seg in segments:
        text = (seg.text if hasattr(seg, 'text') else seg['text']).strip()
        if text:
            non_empty.append(seg)

    removed_empty = len(segments) - len(non_empty)
    if removed_empty > 0:
        sys.stderr.write(f"[DEDUP] Removed {removed_empty} empty/whitespace segments\\n")

    if not non_empty:
        return segments  # 全部空なら元を返す

    # ── Step 2: セグメント内繰り返し除去 ───────────────────────────────────
    for seg in non_empty:
        text = (seg.text if hasattr(seg, 'text') else seg['text']).strip()
        cleaned = remove_intra_repetition(text)
        if cleaned != text:
            sys.stderr.write(f"[DEDUP] Intra-segment fixed: {text!r} -> {cleaned!r}\\n")
            if hasattr(seg, 'text'):
                seg.text = cleaned
            else:
                seg['text'] = cleaned

    # ── Step 3: ウィンドウベースの重複除去 ──────────────────────────────────
    # 直近 WINDOW_SIZE 個のセグメントと比較し、重複なら除去する。
    # ウィンドウを広げることで、空セグメントで連鎖が切れる問題を解消する。
    deduped = []

    for seg in non_empty:
        curr_text = (seg.text if hasattr(seg, 'text') else seg['text']).strip()
        curr_norm = normalize(curr_text)

        is_dup = False
        for prev in deduped[-WINDOW_SIZE:]:
            prev_text = (prev.text if hasattr(prev, 'text') else prev['text']).strip()
            prev_norm = normalize(prev_text)

            # 完全一致
            if curr_norm and curr_norm == prev_norm:
                sys.stderr.write(f"[DEDUP] Exact-window removed: {curr_text!r}\\n")
                is_dup = True
                break

            # Jaccard類似度（短いテキストはより積極的に除去）
            sim = jaccard(curr_text, prev_text)
            thr = similarity_threshold if len(curr_norm) > 5 else 0.75
            if sim >= thr:
                sys.stderr.write(f"[DEDUP] Similar-window removed (sim={sim:.2f}): {curr_text!r}\\n")
                is_dup = True
                break

            # 前のセグメントに包含される短いセグメント（正規化後5文字以下）
            if curr_norm and len(curr_norm) <= 5 and curr_norm in prev_norm:
                sys.stderr.write(f"[DEDUP] Substring-window removed: {curr_text!r}\\n")
                is_dup = True
                break

        if not is_dup:
            deduped.append(seg)

    sys.stderr.write(
        f"[DEDUP] {len(segments)} segs -> {len(non_empty)} (empty removed) -> {len(deduped)} (deduped)\\n"
    )
    sys.stderr.flush()
    return deduped

def correct_transcript_segments(segments: list, batch_size: int = 30,
                                context: str = '') -> list:
    """
    文字起こしセグメントの誤字脱字・変換ミスをOllamaで訂正する。
    タイムスタンプはそのままに、テキストのみ修正する。

    Args:
        segments: SimpleSegment またはオブジェクトのリスト
        batch_size: 一度にOllamaへ送るセグメント数
        context: 配信者・コンテンツ情報の前提文（プロンプトに挿入される）

    Returns:
        訂正済みセグメントのリスト（タイムスタンプ保持）
    """
    try:
        import ollama
        from .config import OLLAMA_MODEL, OLLAMA_HOST
    except ImportError as e:
        sys.stderr.write(f"[CORRECTION] Import error: {e}. Skipping correction.\\n")
        return segments

    corrected_all = []

    for batch_start in range(0, len(segments), batch_size):
        batch = segments[batch_start: batch_start + batch_size]

        # バッチのテキストをJSON配列で送る
        texts = []
        for seg in batch:
            t = seg.text if hasattr(seg, 'text') else seg['text']
            texts.append(t.strip())

        indexed_input = json.dumps(texts, ensure_ascii=False)

        prompt = f"""あなたは日本語の誤字脱字・音声認識ミスの訂正専門家です。
以下のJSON配列は動画の音声を自動文字起こしした結果です。
各テキストを確認し、以下の問題を修正して同じ数・同じ順番のJSON文字列配列として返してください。
{f"\\n【配信情報】\\n{context}\\n（固有名詞・ゲーム用語の訂正にこの情報を活用してください）\\n" if context else ""}
修正すべき問題:
1. 誤字・変換ミス（例: "きた" → "来た"、"もらった" が "もらた" になっている等）
2. 明らかな脱字
3. セグメント内の繰り返しフレーズ（例: "そうですね そうですね そうですね" → "そうですね"）
4. 音声認識特有の同音異義語ミス（文脈から明らかな場合のみ）

重要なルール:
- 配列の要素数を変えてはいけません（{len(texts)}個のまま）
- 意味を変えず、明らかな誤りのみ修正してください
- 修正不要な場合は元のテキストをそのまま返してください
- JSON配列のみ返してください（説明文不要）

入力:
{indexed_input}

修正後のJSON配列:"""

        try:
            sys.stderr.write(f"[CORRECTION] Correcting batch {batch_start//batch_size + 1} ({len(batch)} segments)...\\n")
            sys.stderr.flush()

            client = ollama.Client(host=OLLAMA_HOST, timeout=180.0)
            response = client.chat(
                model=OLLAMA_MODEL,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                }],
                format='json',
                options={'temperature': 0.1, 'num_predict': 2000, 'num_ctx': 32768},
            )

            raw = response['message']['content'].strip()

            # JSON配列として解析
            corrected_texts = None
            try:
                parsed = json.loads(raw)
                # リストとして返ってきた場合
                if isinstance(parsed, list):
                    corrected_texts = parsed
                # {"corrections": [...]} 等のラップ形式
                elif isinstance(parsed, dict):
                    for key in ('corrections', 'texts', 'result', 'results', 'data', 'output'):
                        if key in parsed and isinstance(parsed[key], list):
                            corrected_texts = parsed[key]
                            break
            except json.JSONDecodeError:
                import re
                m = re.search(r'\\[.*?\\]', raw, re.DOTALL)
                if m:
                    try:
                        corrected_texts = json.loads(m.group(0))
                    except Exception:
                        pass

            if corrected_texts and len(corrected_texts) == len(batch):
                # 訂正済みテキストをセグメントに反映
                for seg, new_text in zip(batch, corrected_texts):
                    if isinstance(new_text, str) and new_text.strip():
                        if hasattr(seg, 'text'):
                            seg.text = new_text
                        else:
                            seg['text'] = new_text
                corrected_all.extend(batch)
                sys.stderr.write(f"[CORRECTION] Batch corrected successfully.\\n")
            else:
                sys.stderr.write(f"[CORRECTION] Correction result mismatch (got {len(corrected_texts) if corrected_texts else 'None'}, expected {len(batch)}). Keeping originals for this batch.\\n")
                corrected_all.extend(batch)

        except Exception as e:
            sys.stderr.write(f"[CORRECTION] Error in batch {batch_start//batch_size + 1}: {e}. Keeping originals.\\n")
            sys.stderr.flush()
            corrected_all.extend(batch)

    sys.stderr.write(f"[CORRECTION] Total segments corrected: {len(corrected_all)}\\n")
    sys.stderr.flush()
    return corrected_all
