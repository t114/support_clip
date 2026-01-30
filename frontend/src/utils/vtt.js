export function parseVTT(vttContent) {
    const lines = vttContent.trim().split(/\r?\n/);
    const subtitles = [];
    let currentSubtitle = null;
    let pendingMetadata = null;

    // Simple parser assuming Whisper output format
    // WEBVTT
    //
    // 00:00:00.000 --> 00:00:05.000
    // Text content
    //
    // NOTE metadata:{"styleName":"Default"}

    let textLines = [];

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();

        if (line === 'WEBVTT') continue;

        // Check for metadata comment
        if (line.startsWith('NOTE metadata:')) {
            try {
                const jsonStr = line.substring('NOTE metadata:'.length);
                pendingMetadata = JSON.parse(jsonStr);
            } catch (e) {
                console.warn('Failed to parse metadata:', e);
            }
            continue;
        }

        if (line.includes('-->')) {
            // Save previous subtitle if it existed
            if (currentSubtitle && textLines.length > 0) {
                currentSubtitle.text = textLines.join('\n');
                subtitles.push(currentSubtitle);
            }

            const [start, end] = line.split('-->').map(t => t.trim());
            currentSubtitle = {
                id: generateUUID(),
                start: parseTimestamp(start),
                end: parseTimestamp(end),
                text: '',
                ...(pendingMetadata || {}) // Apply pending metadata
            };
            pendingMetadata = null; // Clear used metadata
            textLines = [];
        } else if (line === '') {
            // Blank line indicates end of current cue text
            if (currentSubtitle && textLines.length > 0) {
                currentSubtitle.text = textLines.join('\n');
                subtitles.push(currentSubtitle);
                currentSubtitle = null;
                textLines = [];
            }
        } else if (currentSubtitle) {
            // Only skip cue numbers (integers on their own line)
            if (/^\d+$/.test(line) && i > 0 && lines[i - 1].trim() === '') {
                continue;
            }
            textLines.push(lines[i]); // Keep original spacing if needed, or trim
        }
    }

    // Don't forget the last subtitle
    if (currentSubtitle && textLines.length > 0) {
        currentSubtitle.text = textLines.join('\n');
        subtitles.push(currentSubtitle);
    }

    return subtitles;
}

export function stringifyVTT(subtitles) {
    let output = 'WEBVTT\n\n';

    for (const sub of subtitles) {
        // Extract metadata (everything except standard fields)
        const { id, start, end, text, ...metadata } = sub;

        // Write metadata if present
        if (Object.keys(metadata).length > 0) {
            output += `NOTE metadata:${JSON.stringify(metadata)}\n\n`;
        }

        output += `${formatTimestamp(sub.start)} --> ${formatTimestamp(sub.end)}\n`;
        output += `${sub.text}\n\n`;
    }

    return output;
}

function parseTimestamp(timestamp) {
    const [hms, ms] = timestamp.split('.');
    const [h, m, s] = hms.split(':').map(Number);
    return h * 3600 + m * 60 + s + (Number(ms) / 1000);
}

function formatTimestamp(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);

    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

export function stringifySRT(subtitles) {
    let output = '';

    for (let i = 0; i < subtitles.length; i++) {
        const sub = subtitles[i];
        output += `${i + 1}\n`;
        output += `${formatTimestampSRT(sub.start)} --> ${formatTimestampSRT(sub.end)}\n`;
        output += `${sub.text}\n\n`;
    }

    return output;
}

function formatTimestampSRT(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);

    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}

export function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}
