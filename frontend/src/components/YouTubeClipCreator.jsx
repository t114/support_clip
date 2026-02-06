import React, { useState, useEffect } from 'react';
import ClipPreview from './ClipPreview';
import DescriptionModal from './DescriptionModal';
import TwitterModal from './TwitterModal';

function YouTubeClipCreator() {
    const [url, setUrl] = useState('');
    const [modelSize, setModelSize] = useState('none');
    const [analysisMode, setAnalysisMode] = useState(false); // 360p download for analysis
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
    const [withComments, setWithComments] = useState(false);
    const [danmakuDensity, setDanmakuDensity] = useState(10); // 0 to 100%

    // Description modal state
    const [isDescriptionModalOpen, setIsDescriptionModalOpen] = useState(false);
    const [generatedDescription, setGeneratedDescription] = useState('');
    // Twitter modal state
    const [detectedMembers, setDetectedMembers] = useState([]);

    // Twitter modal state
    const [isTwitterModalOpen, setIsTwitterModalOpen] = useState(false);
    const [twitterPrText, setTwitterPrText] = useState('');

    // Comments for Danmaku Preview
    const [comments, setComments] = useState([]);

    // Frequent stamps for analysis
    const [topStamps, setTopStamps] = useState([]);
    const [isFetchingTopStamps, setIsFetchingTopStamps] = useState(false);
    const [showTopStamps, setShowTopStamps] = useState(false);

    // Load comments when videoInfo is available and has comments
    useEffect(() => {
        if (videoInfo && videoInfo.has_comments && videoInfo.filename) {
            console.log('Fetching comments for:', videoInfo.filename);
            fetch(`/youtube/comments/${videoInfo.filename}`)
                .then(res => {
                    console.log('Comments API response status:', res.status);
                    return res.json();
                })
                .then(data => {
                    if (data.comments) {
                        console.log(`Loaded ${data.comments.length} comments for preview`);
                        // Add unique IDs to comments to avoid key collisions in DanmakuLayer
                        const commentsWithIds = data.comments.map((c, i) => ({ ...c, id: `comment-${i}` }));
                        setComments(commentsWithIds);
                    } else {
                        console.warn('Comments API returned no comments array');
                    }
                })
                .catch(err => console.error('Failed to load comments:', err));
        } else if (!videoInfo) {
            setComments([]);
        }
    }, [videoInfo]);

    // Fetch all Hololive members for manual addition
    const [allMembers, setAllMembers] = useState([]);
    useEffect(() => {
        fetch('/hololive-members')
            .then(res => res.json())
            .then(data => {
                if (data.members) {
                    setAllMembers(data.members);
                }
            })
            .catch(err => console.error('Failed to load members:', err));
    }, []);

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

    // YouTube URLから動画IDを抽出
    const extractVideoId = (inputUrl) => {
        if (!inputUrl) return null;
        const url = inputUrl.trim();
        try {
            // Try URL object first
            const urlObj = new URL(url);
            if (urlObj.hostname === 'youtu.be') {
                return urlObj.pathname.slice(1);
            }
            if (urlObj.hostname.includes('youtube.com')) {
                return urlObj.searchParams.get('v');
            }
        } catch (e) {
            // URL parsing failed, try regex
        }

        // Regex fallback for various formats (including those without protocol)
        const match = url.match(/(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})/);
        return match ? match[1] : null;
    };

    const handleDownload = async () => {
        if (!url) return;
        const trimmedUrl = url.trim();

        setStatus('downloading');
        setMessage(`YouTube動画をダウンロード中... (モデル: ${modelSize})`);

        // Start polling for progress
        const videoId = extractVideoId(trimmedUrl);
        let progressInterval = null;

        if (videoId) {
            // Poll immediately once
            const checkProgress = async () => {
                try {
                    const res = await fetch(`/progress/${videoId}`);
                    if (res.ok) {
                        const progressData = await res.json();
                        if (progressData.status === 'transcribing') {
                            setMessage(progressData.message || `文字起こし中... ${Math.round(progressData.progress)}%`);
                        } else if (progressData.status === 'downloading') {
                            setMessage(progressData.message || '動画をダウンロード中...');
                        } else if (progressData.status === 'completed') {
                            // Optional: update message if needed, but main request should finish soon
                            // setMessage('処理完了。結果を取得中...');
                        }
                    }
                } catch (e) {
                    // Ignore polling errors
                }
            };

            checkProgress();
            progressInterval = setInterval(checkProgress, 1000);
        } else {
            console.warn("Could not extract video ID for polling");
        }

        try {
            console.log('[DOWNLOAD] Starting download request...');
            const response = await fetch('/youtube/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: trimmedUrl,
                    with_comments: withComments,
                    model_size: modelSize,
                    analysis_mode: analysisMode
                })
            });

            console.log('[DOWNLOAD] Response received:', response.status);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMsg = errorData.detail || `ダウンロードに失敗しました (ステータス: ${response.status})`;
                throw new Error(errorMsg);
            }

            console.log('[DOWNLOAD] Parsing response JSON...');
            const data = await response.json();
            console.log('[DOWNLOAD] Response data:', data);
            console.log('[DOWNLOAD] has_comments:', data.has_comments);
            console.log('[DOWNLOAD] video_info:', data.video_info);

            // video_infoにhas_commentsとfilenameを追加
            const videoInfoWithComments = {
                ...data.video_info,
                has_comments: data.has_comments,
                filename: data.filename
            };
            setVideoInfo(videoInfoWithComments);

            setVideoUrl(data.video_url);
            setVttUrl(data.subtitle_url);
            setSrtUrl(data.srt_url);
            setFcpxmlUrl(data.fcpxml_url);

            // subtitle_urlがnullでない場合のみfilenameを設定
            if (data.subtitle_url) {
                setVttFilename(data.subtitle_url.split('/').pop());
            }

            // バックエンドから返されたstart_timeを使用（URLから抽出済み）
            if (data.start_time !== undefined && data.start_time > 0) {
                setStartTime(data.start_time);
            }

            // Reset analysis state
            setClips([]);
            setAnalysisOffset(0);
            setHasMore(false);

            // 字幕がない場合（文字起こしをスキップした場合）
            if (!data.subtitle_url) {
                setStatus('ready');
                setMessage('✓ 動画のダウンロードが完了しました。字幕ファイルをアップロードしてください。');
            } else {
                // 字幕がある場合は解析方法の選択を待つ
                setStatus('ready');

                // キャッシュ使用時のメッセージ
                if (data.cached) {
                    if (withComments && !data.has_comments) {
                        setMessage('✓ キャッシュされた動画を使用しています。コメントデータをダウンロード中...');
                    } else {
                        setMessage('✓ ダウンロード完了！解析方法を選択してください。');
                    }
                } else {
                    setMessage('✓ ダウンロード完了！解析方法を選択してください。');
                }
            }

        } catch (e) {
            console.error(e);
            setStatus('error');
            setMessage('エラーが発生しました: ' + e.message);
        } finally {
            if (progressInterval) {
                clearInterval(progressInterval);
            }
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

    const handleAnalyzeStamps = async (category, customPattern = null) => {
        try {
            setStatus('analyzing');
            const catName = customPattern ? `スタンプ「${customPattern}」` : (category === 'kusa' ? '草' : 'カワイイ');
            setMessage(`${catName}シーンを分析中...`);

            const response = await fetch('/youtube/analyze-stamps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    vtt_filename: vttFilename,
                    video_filename: videoInfo?.filename,
                    category: category,
                    custom_patterns: customPattern ? [customPattern] : null,
                    clip_duration: 60
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `${catName}分析に失敗しました`);
            }

            const data = await response.json();

            if (data.clips && data.clips.length > 0) {
                const clipsWithIds = data.clips.map((c, i) => ({ ...c, id: Date.now() + i }));
                setClips(clipsWithIds);
                setMessage(`${catName}盛り上がりシーンが見つかりました (${data.total_clips}件)`);
            } else {
                setMessage(data.message || `${catName}シーンが見つかりませんでした`);
            }

            setStatus('ready');
        } catch (e) {
            console.error(e);
            setStatus('ready');
            setMessage(e.message);
        }
    };

    const handleFetchTopStamps = async () => {
        if (!videoInfo?.filename && !vttFilename) return;
        setIsFetchingTopStamps(true);
        try {
            const res = await fetch('/youtube/top-stamps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    vtt_filename: vttFilename,
                    video_filename: videoInfo?.filename
                })
            });
            if (!res.ok) throw new Error('頻出スタンプの取得に失敗しました');
            const data = await res.json();
            setTopStamps(data.top_stamps || []);
            setShowTopStamps(true);
        } catch (e) {
            alert(e.message);
        } finally {
            setIsFetchingTopStamps(false);
        }
    };


    const analyzeCommentDensity = async () => {
        try {
            setStatus('analyzing');
            setMessage('コメント量を分析中...');

            const response = await fetch('/youtube/analyze-comment-density', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    vtt_filename: vttFilename,
                    video_filename: videoInfo?.filename,
                    clip_duration: 60
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Comment density analysis failed');
            }

            const data = await response.json();

            if (data.clips && data.clips.length > 0) {
                // Add IDs to clips
                const clipsWithIds = data.clips.map((c, i) => ({ ...c, id: Date.now() + i }));

                // Replace existing clips with comment density clips
                setClips(clipsWithIds);
                setMessage(`コメント量クリップが見つかりました (${data.total_clips}件)`);
            } else {
                setMessage(data.message || 'コメントを含むクリップが見つかりませんでした');
            }

            setStatus('ready');

        } catch (e) {
            console.error(e);
            setStatus('ready');
            setMessage('コメント量分析に失敗しました: ' + e.message);
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

    const generateDescription = async () => {
        try {
            if (!videoInfo) {
                alert('動画情報がありません');
                return;
            }

            const response = await fetch('/generate-description', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    original_url: url,
                    original_title: videoInfo.title || '',
                    video_description: videoInfo.description || '',
                    clip_title: null,
                    upload_date: videoInfo.upload_date || null
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            setGeneratedDescription(data.description);
            setDetectedMembers(data.detected_members || []);
            setIsDescriptionModalOpen(true);
        } catch (error) {
            console.error('Error generating description:', error);
            alert(`概要欄の生成に失敗しました: ${error.message}`);
        }
    };

    const generateTwitterPR = async () => {
        try {
            if (!videoInfo) {
                alert('動画情報がありません');
                return;
            }

            setMessage('PR文章を生成中...');
            const response = await fetch('/generate-twitter-pr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    original_url: url,
                    original_title: videoInfo.title || '',
                    video_description: videoInfo.description || '',
                    clip_title: null,
                    upload_date: videoInfo.upload_date || null
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            setTwitterPrText(data.pr_text);
            setIsTwitterModalOpen(true);
            setMessage('PR文章を生成しました');
        } catch (error) {
            console.error('Error generating Twitter PR:', error);
            setMessage(`PR文章の生成に失敗しました: ${error.message}`);
        }
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
                    title: clip.title,
                    crop_x: clip.crop_x,
                    crop_y: clip.crop_y,
                    crop_width: clip.crop_width,
                    crop_height: clip.crop_height,
                    with_danmaku: clip.with_danmaku,
                    danmaku_density: clip.danmaku_density,
                    aspect_ratio: clip.aspect_ratio,
                    use_obs_capture: clip.use_obs_capture // Pass OBS capture flag
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

                <div className="flex gap-2">
                    <input
                        type="text"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="YouTube URL (例: https://www.youtube.com/watch?v=...)"
                        className="flex-1 p-2 border rounded"
                    />
                    <select
                        value={modelSize}
                        onChange={(e) => setModelSize(e.target.value)}
                        className="p-2 border rounded bg-white"
                        title="文字起こしモデルのサイズ（精度と速度のトレードオフ）"
                    >
                        <option value="none">none (文字起こししない)</option>
                        <option value="tiny">tiny (最速・低精度)</option>
                        <option value="base">base (推奨・バランス)</option>
                        <option value="small">small (高精度・遅い)</option>
                        <option value="medium">medium (超高精度・激遅)</option>
                        <option value="large">large (最高精度・激重)</option>
                    </select>
                    <button
                        onClick={handleDownload}
                        disabled={status === 'downloading' || !url}
                        className="bg-red-600 text-white px-6 py-2 rounded hover:bg-red-700 disabled:bg-gray-400"
                    >
                        {status === 'downloading' ? '処理中...' : '開始'}
                    </button>
                </div>

                <div className="mb-2 mt-2">
                    <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={analysisMode}
                            onChange={(e) => setAnalysisMode(e.target.checked)}
                            disabled={status === 'downloading'}
                            className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                        />
                        <span>分析モードでダウンロード (360p/高速) - クリップ作成時にOBSで高画質キャプチャします</span>
                    </label>
                </div>

                <div className="mb-4">
                    <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={withComments}
                            onChange={(e) => setWithComments(e.target.checked)}
                            disabled={status === 'downloading' || status === 'analyzing'}
                            className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                        />
                        <span>コメント/チャットも取得して分析する（時間がかかる場合があります）</span>
                    </label>
                    {withComments && (
                        <div className="mt-2 flex items-center gap-4 pl-6">
                            <span className="text-xs font-medium text-gray-600 whitespace-nowrap">コメント表示濃度:</span>
                            <input
                                type="range"
                                min="1"
                                max="100"
                                step="1"
                                value={danmakuDensity}
                                onChange={(e) => setDanmakuDensity(parseInt(e.target.value))}
                                className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-600"
                            />
                            <span className="text-xs font-bold text-red-600 w-8">{danmakuDensity}%</span>
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-3 mb-4 p-3 bg-gray-50 rounded-md border border-gray-200">
                    <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
                        解析開始位置:
                    </label>
                    <div className="flex items-center gap-2">
                        <input
                            type="number"
                            value={Math.floor(startTime / 3600)}
                            onChange={(e) => {
                                const hours = parseInt(e.target.value) || 0;
                                const minutes = Math.floor((startTime % 3600) / 60);
                                const seconds = startTime % 60;
                                setStartTime(Math.max(0, hours * 3600 + minutes * 60 + seconds));
                            }}
                            min="0"
                            className="w-16 rounded-md border-gray-300 border p-2 text-sm"
                            disabled={status === 'downloading' || status === 'analyzing'}
                            placeholder="0"
                        />
                        <span className="text-sm text-gray-600">時間</span>
                        <input
                            type="number"
                            value={Math.floor((startTime % 3600) / 60)}
                            onChange={(e) => {
                                const hours = Math.floor(startTime / 3600);
                                const minutes = parseInt(e.target.value) || 0;
                                const seconds = startTime % 60;
                                setStartTime(Math.max(0, hours * 3600 + minutes * 60 + seconds));
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
                                const hours = Math.floor(startTime / 3600);
                                const minutes = Math.floor((startTime % 3600) / 60);
                                const seconds = parseInt(e.target.value) || 0;
                                setStartTime(Math.max(0, hours * 3600 + minutes * 60 + Math.min(59, seconds)));
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
                        <div className="flex items-center gap-2 mt-1">
                            <p className="text-sm text-gray-600">長さ: {videoInfo.duration}秒</p>
                            {((videoInfo.has_comments || withComments)) && (
                                <div className="flex items-center gap-2">
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${comments.length > 0 ? 'bg-green-100 text-green-700' : (videoInfo.has_comments ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700')}`}>
                                        コメント: {videoInfo.has_comments ? (comments.length > 0 ? `${comments.length}件 ✓` : '読み込み中...') : 'データなし ✗'}
                                    </span>
                                </div>
                            )}
                        </div>
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
                        <div className="mt-4 flex gap-2 flex-wrap">
                            {!vttUrl && videoInfo && (
                                <div className="w-full mb-2">
                                    <label className="text-sm bg-yellow-100 text-yellow-800 px-3 py-2 rounded inline-flex items-center gap-2 cursor-pointer hover:bg-yellow-200">
                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                        </svg>
                                        字幕ファイルをアップロード (VTT/SRT)
                                        <input
                                            type="file"
                                            accept=".vtt,.srt"
                                            className="hidden"
                                            onChange={async (e) => {
                                                const file = e.target.files[0];
                                                if (!file) return;

                                                const formData = new FormData();
                                                formData.append('file', file);
                                                formData.append('video_filename', videoInfo.filename);

                                                try {
                                                    setMessage('字幕ファイルをアップロード中...');
                                                    const response = await fetch('/youtube/upload-subtitle', {
                                                        method: 'POST',
                                                        body: formData
                                                    });

                                                    if (!response.ok) {
                                                        throw new Error('字幕アップロードに失敗しました');
                                                    }

                                                    const data = await response.json();
                                                    if (data.subtitle_url) {
                                                        setVttUrl(data.subtitle_url);
                                                        const vttFilename = data.subtitle_url.split('/').pop();
                                                        setVttFilename(vttFilename);

                                                        // 字幕アップロード後、解析方法の選択を待つ
                                                        setMessage('字幕ファイルがアップロードされました。解析方法を選択してください。');

                                                        // Reset analysis state
                                                        setClips([]);
                                                        setAnalysisOffset(0);
                                                        setHasMore(false);
                                                    }
                                                    if (data.srt_url) {
                                                        setSrtUrl(data.srt_url);
                                                    }
                                                    if (data.fcpxml_url) {
                                                        setFcpxmlUrl(data.fcpxml_url);
                                                    }
                                                } catch (error) {
                                                    console.error('Error uploading subtitle:', error);
                                                    setMessage(`エラー: ${error.message}`);
                                                    setStatus('error');
                                                } finally {
                                                    // ファイル入力をリセット（同じファイルを再度選択可能にする）
                                                    e.target.value = '';
                                                }
                                            }}
                                        />
                                    </label>
                                </div>
                            )}
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

                        {/* 解析方法選択ボタン（クリップがない場合に表示） */}
                        {(vttFilename || videoInfo?.has_comments) && clips.length === 0 && status === 'ready' && (
                            <div className="mt-4 p-4 bg-blue-50 rounded-lg border-2 border-blue-200">
                                <h4 className="font-bold text-blue-900 mb-3 text-center">解析方法を選択してください</h4>
                                <div className="flex gap-3 justify-center flex-wrap">
                                    {vttFilename && (
                                        <button
                                            onClick={() => {
                                                setStatus('analyzing');
                                                setMessage('AIが動画を分析中...');
                                                analyzeVideo(vttFilename, 0);
                                            }}
                                            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                            </svg>
                                            AI解析
                                        </button>
                                    )}
                                    {videoInfo?.has_comments && (
                                        <>
                                            <button
                                                onClick={analyzeCommentDensity}
                                                className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                                </svg>
                                                コメント量解析
                                            </button>
                                            <button
                                                onClick={() => handleAnalyzeStamps('kusa')}
                                                className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
                                            >
                                                <span className="text-xl">🌱</span>
                                                草解析
                                            </button>
                                            <button
                                                onClick={() => handleAnalyzeStamps('kawaii')}
                                                className="px-6 py-3 bg-pink-500 text-white rounded-lg hover:bg-pink-600 transition-colors flex items-center gap-2"
                                            >
                                                <span className="text-xl">💕</span>
                                                カワイイ解析
                                            </button>
                                            <button
                                                onClick={handleFetchTopStamps}
                                                disabled={isFetchingTopStamps}
                                                className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-2"
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                                </svg>
                                                {isFetchingTopStamps ? '集計中...' : '集計スタンプ解析'}
                                            </button>
                                        </>
                                    )}
                                </div>

                                {showTopStamps && topStamps.length > 0 && (
                                    <div className="mt-6 border-t pt-4">
                                        <div className="flex justify-between items-center mb-3">
                                            <h5 className="font-bold text-indigo-900 flex items-center gap-1">
                                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                                                </svg>
                                                頻出スタンプランキング (上位20件)
                                            </h5>
                                            <button onClick={() => setShowTopStamps(false)} className="text-gray-400 hover:text-gray-600">
                                                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                                </svg>
                                            </button>
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            {topStamps.map((s, idx) => (
                                                <button
                                                    key={idx}
                                                    onClick={() => handleAnalyzeStamps(null, s.shortcut)}
                                                    className="group flex items-center gap-2 bg-white border border-indigo-200 hover:border-indigo-400 hover:bg-indigo-50 px-3 py-2 rounded-full shadow-sm transition-all"
                                                    title={`${s.shortcut} で盛り上がり箇所を解析`}
                                                >
                                                    <span className="font-mono text-sm text-indigo-700">{s.shortcut}</span>
                                                    <span className="bg-indigo-100 text-indigo-800 text-[10px] px-1.5 py-0.5 rounded-full font-bold group-hover:bg-indigo-200">
                                                        {s.count}
                                                    </span>
                                                </button>
                                            ))}
                                        </div>
                                        <p className="text-xs text-indigo-500 mt-3">
                                            ※ スタンプをクリックすると、そのスタンプの使用密度に基づいた盛り上がり解析を実行します。
                                        </p>
                                    </div>
                                )}
                                {showTopStamps && topStamps.length === 0 && !isFetchingTopStamps && (
                                    <p className="text-center text-sm text-gray-500 mt-4 italic">
                                        スタンプの使用データが見つかりませんでした。
                                    </p>
                                )}
                                {!videoInfo?.has_comments && (
                                    <p className="text-sm text-gray-600 mt-3 text-center">
                                        ※ コメント解析を使用するには、動画ダウンロード時に「コメント/チャットも取得」にチェックを入れてください
                                    </p>
                                )}
                                {!vttFilename && videoInfo?.has_comments && (
                                    <p className="text-sm text-gray-600 mt-3 text-center">
                                        ※ 文字起こしデータがないため、AI解析は使用できません（コメント解析のみ可能です）
                                    </p>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {
                status === 'ready' && (
                    <div className="space-y-6">
                        <div className="flex justify-between items-center">
                            <h3 className="text-xl font-bold">切り抜き候補 ({clips.length}件)</h3>
                            <div className="flex gap-2 flex-wrap">
                                {hasMore && (
                                    <button
                                        onClick={handleAnalyzeMore}
                                        className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
                                    >
                                        さらに解析
                                    </button>
                                )}
                                {videoInfo?.has_comments && vttFilename && (
                                    <>
                                        <button
                                            onClick={analyzeCommentDensity}
                                            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 flex items-center gap-1"
                                            title="コメント量で切り抜き候補を検出"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                            </svg>
                                            コメント量で解析
                                        </button>
                                        <button
                                            onClick={analyzeKusaClips}
                                            className="bg-yellow-500 text-white px-4 py-2 rounded hover:bg-yellow-600 flex items-center gap-1"
                                            title="コメント内の草絵文字の使用頻度で切り抜き候補を検出"
                                        >
                                            <span>🌱</span>
                                            草絵文字で解析
                                        </button>
                                    </>
                                )}
                                <button
                                    onClick={generateDescription}
                                    className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                                >
                                    概要欄を生成
                                </button>
                                <button
                                    onClick={generateTwitterPR}
                                    className="bg-sky-500 text-white px-4 py-2 rounded hover:bg-sky-600 flex items-center gap-1"
                                >
                                    <span>🐦</span>
                                    PR文章を生成
                                </button>
                                <button
                                    onClick={addManualClip}
                                    className="bg-gray-200 text-gray-800 px-4 py-2 rounded hover:bg-gray-300"
                                >
                                    + 手動で追加
                                </button>
                            </div>
                        </div>

                        <div className="space-y-4">
                            {clips.map(clip => {
                                // console.log('Rendering ClipPreview, filename:', videoInfo?.filename);
                                return (
                                    <ClipPreview
                                        key={clip.id}
                                        clip={clip}
                                        videoUrl={videoUrl}
                                        onUpdate={updateClip}
                                        onDelete={deleteClip}
                                        onCreate={createClip}
                                        isCreating={creatingClipId === clip.id}
                                        comments={comments}
                                        danmakuDensity={danmakuDensity}
                                        channelId={videoInfo?.channel_id}
                                        videoFilename={videoInfo?.filename}
                                        defaultUseObs={analysisMode} // Pass analysis mode as default for OBS capture
                                    />
                                );
                            })}
                        </div>

                        {clips.length === 0 && (
                            <div className="text-center text-gray-500 py-8">
                                クリップ候補がありません。手動で追加してください。
                            </div>
                        )}
                    </div>
                )
            }

            {isDescriptionModalOpen && (
                <DescriptionModal
                    isOpen={isDescriptionModalOpen}
                    onClose={() => setIsDescriptionModalOpen(false)}
                    initialDescription={generatedDescription}
                    detectedMembers={detectedMembers}
                    allMembers={allMembers}
                />
            )}
            <TwitterModal
                isOpen={isTwitterModalOpen}
                onClose={() => setIsTwitterModalOpen(false)}
                initialText={twitterPrText}
            />
        </div>
    );
}

export default YouTubeClipCreator;
