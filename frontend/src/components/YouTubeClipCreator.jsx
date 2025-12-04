import React, { useState } from 'react';
import ClipPreview from './ClipPreview';

function YouTubeClipCreator() {
    const [url, setUrl] = useState('');
    const [status, setStatus] = useState('idle'); // idle, downloading, analyzing, ready
    const [videoInfo, setVideoInfo] = useState(null);
    const [clips, setClips] = useState([]);
    const [message, setMessage] = useState('');
    const [videoUrl, setVideoUrl] = useState('');
    const [vttUrl, setVttUrl] = useState('');
    const [srtUrl, setSrtUrl] = useState('');
    const [fcpxmlUrl, setFcpxmlUrl] = useState('');
    const [vttFilename, setVttFilename] = useState('');
    const [analysisOffset, setAnalysisOffset] = useState(0);
    const [hasMore, setHasMore] = useState(false);
    const [totalSegments, setTotalSegments] = useState(0);
    const [analyzedSegments, setAnalyzedSegments] = useState(0);
    const [creatingClipId, setCreatingClipId] = useState(null);
    const [startTime, setStartTime] = useState(0);

    // YouTube URLからt=パラメータを抽出
    const extractStartTimeFromUrl = (url) => {
        try {
            const urlObj = new URL(url);
            const t = urlObj.searchParams.get('t');

            if (!t) return 0;

            // 数値のみの場合（秒）
            if (/^\d+$/.test(t)) {
                return parseInt(t);
            }

            // h/m/s形式の場合
            const hours = t.match(/(\d+)h/);
            const minutes = t.match(/(\d+)m/);
            const seconds = t.match(/(\d+)s/);

            let totalSeconds = 0;
            if (hours) totalSeconds += parseInt(hours[1]) * 3600;
            if (minutes) totalSeconds += parseInt(minutes[1]) * 60;
            if (seconds) totalSeconds += parseInt(seconds[1]);

            return totalSeconds;
        } catch (e) {
            return 0;
        }
    };

    const handleUrlChange = (e) => {
        const newUrl = e.target.value;
        setUrl(newUrl);

        // t=パラメータを自動抽出
        const extractedTime = extractStartTimeFromUrl(newUrl);
        if (extractedTime > 0) {
            setStartTime(extractedTime);
        }
    };

    const handleDownload = async () => {
        if (!url) return;
        setStatus('downloading');
        setMessage('YouTube動画をダウンロード中... (これには時間がかかる場合があります)');

        try {
            const response = await fetch('/youtube/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMsg = errorData.detail || `ダウンロードに失敗しました (ステータス: ${response.status})`;
                throw new Error(errorMsg);
            }

            const data = await response.json();
            setVideoInfo(data.video_info);
            setVideoUrl(data.video_url);
            setVttUrl(data.subtitle_url);
            setSrtUrl(data.srt_url);
            setFcpxmlUrl(data.fcpxml_url);
            setVttFilename(data.subtitle_url.split('/').pop()); // Extract filename

            // バックエンドから返されたstart_timeを使用（URLから抽出済み）
            if (data.start_time !== undefined && data.start_time > 0) {
                setStartTime(data.start_time);
            }

            setStatus('analyzing');
            setMessage('AIが動画を分析して切り抜き箇所を探しています...');

            // Reset analysis state
            setClips([]);
            setAnalysisOffset(0);
            setHasMore(false);

            // Auto-start analysis
            analyzeVideo(data.subtitle_url.split('/').pop(), 0);

        } catch (e) {
            console.error(e);
            setStatus('error');
            setMessage('エラーが発生しました: ' + e.message);
        }
    };

    const analyzeVideo = async (vttFile, offset = 0) => {
        try {
            setStatus('analyzing');
            setMessage(`AIが動画を分析中... (${offset}セグメント目から)`);

            const response = await fetch('/youtube/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    vtt_filename: vttFile,
                    max_clips: 5,
                    offset: offset,
                    start_time: startTime
                })
            });

            if (!response.ok) throw new Error('Analysis failed');

            const data = await response.json();

            // Add IDs to clips
            const clipsWithIds = data.clips.map((c, i) => ({ ...c, id: Date.now() + i }));

            // Append new clips to existing ones
            setClips(prevClips => [...prevClips, ...clipsWithIds]);

            // Update analysis metadata
            setTotalSegments(data.total_segments);
            setAnalyzedSegments(data.analyzed_segments);
            setHasMore(data.has_more);
            setAnalysisOffset(data.next_offset || 0);

            setStatus('ready');

            if (data.has_more) {
                setMessage(`切り抜き候補が見つかりました (${data.analyzed_segments}/${data.total_segments}セグメント分析済み)`);
            } else {
                setMessage(`全ての切り抜き候補が見つかりました (${data.total_segments}セグメント完了)`);
            }

        } catch (e) {
            console.error(e);
            setStatus('ready'); // Allow manual creation even if AI fails
            setMessage('AI分析に失敗しましたが、手動で作成できます: ' + e.message);
        }
    };

    const handleAnalyzeMore = () => {
        if (vttFilename && hasMore) {
            analyzeVideo(vttFilename, analysisOffset);
        }
    };

    const addManualClip = () => {
        const newClip = {
            id: Date.now(),
            start: 0,
            end: 10,
            title: '新規クリップ',
            reason: '手動追加'
        };
        setClips([...clips, newClip]);
    };

    const updateClip = (updatedClip) => {
        setClips(clips.map(c => c.id === updatedClip.id ? updatedClip : c));
    };

    const deleteClip = (id) => {
        setClips(clips.filter(c => c.id !== id));
    };

    const createClip = async (clip) => {
        try {
            setCreatingClipId(clip.id);
            setMessage(`クリップ「${clip.title}」を作成中...`);
            const response = await fetch('/youtube/create-clip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_filename: videoInfo.filename,
                    start: clip.start,
                    end: clip.end,
                    title: clip.title
                })
            });

            if (!response.ok) throw new Error('Creation failed');

            const data = await response.json();

            // Trigger download
            const link = document.createElement('a');
            link.href = `/download/${data.filename}`;
            link.download = data.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            setMessage(`クリップ「${clip.title}」を作成しました`);

        } catch (e) {
            console.error(e);
            setMessage('クリップ作成エラー: ' + e.message);
        } finally {
            setCreatingClipId(null);
        }
    };

    return (
        <div className="max-w-4xl mx-auto p-4">
            <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
                <h2 className="text-2xl font-bold mb-4">YouTube切り抜き作成</h2>

                <div className="flex gap-2 mb-4">
                    <input
                        type="text"
                        value={url}
                        onChange={handleUrlChange}
                        placeholder="YouTube URLを入力 (例: https://www.youtube.com/watch?v=...)"
                        className="flex-1 rounded-md border-gray-300 border p-2"
                        disabled={status === 'downloading' || status === 'analyzing'}
                    />
                    <button
                        onClick={handleDownload}
                        disabled={!url || status === 'downloading' || status === 'analyzing'}
                        className="bg-red-600 text-white px-6 py-2 rounded-md hover:bg-red-700 disabled:bg-red-300"
                    >
                        {status === 'downloading' ? 'ダウンロード中...' : '開始'}
                    </button>
                </div>

                <div className="flex items-center gap-3 mb-4 p-3 bg-gray-50 rounded-md border border-gray-200">
                    <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
                        解析開始位置:
                    </label>
                    <div className="flex items-center gap-2">
                        <input
                            type="number"
                            value={Math.floor(startTime / 60)}
                            onChange={(e) => {
                                const minutes = parseInt(e.target.value) || 0;
                                const seconds = startTime % 60;
                                setStartTime(Math.max(0, minutes * 60 + seconds));
                            }}
                            min="0"
                            className="w-16 rounded-md border-gray-300 border p-2 text-sm"
                            disabled={status === 'downloading' || status === 'analyzing'}
                            placeholder="0"
                        />
                        <span className="text-sm text-gray-600">分</span>
                        <input
                            type="number"
                            value={startTime % 60}
                            onChange={(e) => {
                                const minutes = Math.floor(startTime / 60);
                                const seconds = parseInt(e.target.value) || 0;
                                setStartTime(Math.max(0, minutes * 60 + Math.min(59, seconds)));
                            }}
                            min="0"
                            max="59"
                            className="w-16 rounded-md border-gray-300 border p-2 text-sm"
                            disabled={status === 'downloading' || status === 'analyzing'}
                            placeholder="0"
                        />
                        <span className="text-sm text-gray-600">秒</span>
                    </div>
                    {startTime > 0 && (
                        <span className="text-sm text-blue-600 font-medium">
                            (合計: {startTime}秒)
                        </span>
                    )}
                    <span className="text-xs text-gray-500 ml-auto">
                        OP/イントロをスキップする場合に設定
                    </span>
                </div>

                {message && (
                    <div className={`p-3 rounded mb-4 ${status === 'error' ? 'bg-red-100 text-red-700' : 'bg-blue-50 text-blue-700'}`}>
                        {message}
                    </div>
                )}

                {videoInfo && (
                    <div className="mb-6 p-4 bg-gray-50 rounded border">
                        <h3 className="font-bold">{videoInfo.title}</h3>
                        <p className="text-sm text-gray-600">長さ: {videoInfo.duration}秒</p>
                        {totalSegments > 0 && (
                            <div className="mt-2">
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 bg-gray-200 rounded-full h-2">
                                        <div
                                            className="bg-blue-600 h-2 rounded-full transition-all"
                                            style={{ width: `${(analyzedSegments / totalSegments) * 100}%` }}
                                        ></div>
                                    </div>
                                    <span className="text-xs text-gray-600">
                                        {analyzedSegments}/{totalSegments}
                                    </span>
                                </div>
                            </div>
                        )}
                        <div className="mt-4 flex gap-2">
                            {vttUrl && (
                                <a
                                    href={vttUrl}
                                    download
                                    className="text-sm bg-gray-200 hover:bg-gray-300 text-gray-800 px-3 py-1 rounded inline-flex items-center gap-1"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                    VTTをダウンロード
                                </a>
                            )}
                            {srtUrl && (
                                <a
                                    href={srtUrl}
                                    download
                                    className="text-sm bg-gray-200 hover:bg-gray-300 text-gray-800 px-3 py-1 rounded inline-flex items-center gap-1"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                    SRTをダウンロード
                                </a>
                            )}
                            {fcpxmlUrl && (
                                <a
                                    href={fcpxmlUrl}
                                    download
                                    className="text-sm bg-purple-200 hover:bg-purple-300 text-purple-800 px-3 py-1 rounded inline-flex items-center gap-1"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                    FCPXML (DaVinci)
                                </a>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {
                status === 'ready' && (
                    <div className="space-y-6">
                        <div className="flex justify-between items-center">
                            <h3 className="text-xl font-bold">切り抜き候補 ({clips.length}件)</h3>
                            <div className="flex gap-2">
                                {hasMore && (
                                    <button
                                        onClick={handleAnalyzeMore}
                                        className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
                                    >
                                        さらに解析
                                    </button>
                                )}
                                <button
                                    onClick={addManualClip}
                                    className="bg-gray-200 text-gray-800 px-4 py-2 rounded hover:bg-gray-300"
                                >
                                    + 手動で追加
                                </button>
                            </div>
                        </div>

                        <div className="space-y-4">
                            {clips.map(clip => (
                                <ClipPreview
                                    key={clip.id}
                                    clip={clip}
                                    videoUrl={videoUrl}
                                    onUpdate={updateClip}
                                    onDelete={deleteClip}
                                    onCreate={createClip}
                                    isCreating={creatingClipId === clip.id}
                                />
                            ))}
                        </div>

                        {clips.length === 0 && (
                            <div className="text-center text-gray-500 py-8">
                                クリップ候補がありません。手動で追加してください。
                            </div>
                        )}
                    </div>
                )
            }
        </div >
    );
}

export default YouTubeClipCreator;
