import React, { useState, useRef, useEffect } from 'react';
import DanmakuLayer from './DanmakuLayer';

// Helper to get coordinates relative to an element
const getRelativePos = (e, element) => {
    const rect = element.getBoundingClientRect();
    return {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
    };
};

function ClipPreview({
    clip,
    videoUrl,
    onUpdate,
    onDelete,
    onCreate,
    isCreating,
    comments,
    danmakuDensity = 10,
    channelId,
    videoFilename
}) {
    // Debug log
    // console.log(`ClipPreview: videoFilename=${videoFilename}`);

    const videoRef = useRef(null);
    const containerRef = useRef(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [localClip, setLocalClip] = useState(clip);
    const [currentTime, setCurrentTime] = useState(0);
    const [showDanmaku, setShowDanmaku] = useState(true);

    // Crop state
    const [showCrop, setShowCrop] = useState(false);
    const [cropMode, setCropMode] = useState('horizontal'); // 'horizontal' (16:9) or 'vertical' (9:16)
    const [cropRect, setCropRect] = useState(null); // { x, y, width, height } in percentages (0-100)
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState(null); // { x, y } in pixels
    const [rectStart, setRectStart] = useState(null); // { x, y } in percentages

    // Reference Comments
    const [referenceComments, setReferenceComments] = useState([]);
    const [showReferenceComments, setShowReferenceComments] = useState(false);
    const [isFetchingReference, setIsFetchingReference] = useState(false);


    // Video natural dimensions
    const [videoDims, setVideoDims] = useState({ width: 0, height: 0 });

    useEffect(() => {
        setLocalClip(clip);
        if (clip.crop_width) {
            setShowCrop(true);
        }
    }, [clip]);

    // Recalculate crop when video dimensions are loaded to ensure aspect ratio is correct
    useEffect(() => {
        const dims = getSafeVideoDims();
        const hasRealDims = videoRef.current && videoRef.current.videoWidth > 0;

        // Sync state if needed (fixes container aspect ratio)
        if (hasRealDims) {
            if (videoDims.width !== videoRef.current.videoWidth || videoDims.height !== videoRef.current.videoHeight) {
                setVideoDims({
                    width: videoRef.current.videoWidth,
                    height: videoRef.current.videoHeight
                });
                return; // Let re-render handle the rest
            }
        }

        if (!hasRealDims && !videoDims.width) return;

        if (localClip.crop_width && showCrop) {
            const currentDims = hasRealDims ? { width: videoRef.current.videoWidth, height: videoRef.current.videoHeight } : videoDims;
            // Restore from saved pixels
            const x = (localClip.crop_x / currentDims.width) * 100;
            const y = (localClip.crop_y / currentDims.height) * 100;
            const w = (localClip.crop_width / currentDims.width) * 100;
            const h = (localClip.crop_height / currentDims.height) * 100;
            setCropRect({ x, y, width: w, height: h });
        } else if (showCrop && hasRealDims) {
            // If active and we just got dimensions, re-init to ensure correct aspect
            initCropRect(cropMode);
        }
    }, [videoDims.width, videoDims.height, videoRef.current?.readyState]); // Use readyState to trigger check

    const handleLoadedMetadata = () => {
        if (videoRef.current) {
            setVideoDims({
                width: videoRef.current.videoWidth,
                height: videoRef.current.videoHeight
            });
        }
    };

    useEffect(() => {
        if (videoRef.current && videoRef.current.readyState >= 1) {
            handleLoadedMetadata();
        }
    }, [videoUrl]);

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            const currentTime = videoRef.current.currentTime;
            setCurrentTime(currentTime);
            if (currentTime >= localClip.end) {
                videoRef.current.pause();
                setIsPlaying(false);
                videoRef.current.currentTime = localClip.start;
            }
        }
    };

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const playPreview = () => {
        if (videoRef.current) {
            videoRef.current.currentTime = localClip.start;
            videoRef.current.play();
            setIsPlaying(true);
        }
    };

    const stopPreview = () => {
        if (videoRef.current) {
            videoRef.current.pause();
            setIsPlaying(false);
        }
    };

    const handleChange = (field, value) => {
        const updated = { ...localClip, [field]: value };
        setLocalClip(updated);
        onUpdate(updated);
    };

    // Crop Logic
    const toggleCrop = () => {
        const newState = !showCrop;
        setShowCrop(newState);

        if (newState && !cropRect) {
            // Initialize crop rect centered
            initCropRect(cropMode);
        } else if (!newState) {
            // Clear crop data from clip when disabled
            const updated = { ...localClip };
            delete updated.crop_x;
            delete updated.crop_y;
            delete updated.crop_width;
            delete updated.crop_height;
            setLocalClip(updated);
            onUpdate(updated);
        }
    };

    const getSafeVideoDims = () => {
        if (videoDims.width && videoDims.height) return videoDims;
        if (videoRef.current && videoRef.current.videoWidth) {
            return {
                width: videoRef.current.videoWidth,
                height: videoRef.current.videoHeight
            };
        }
        return { width: 16, height: 9 }; // Fallback
    };

    const initCropRect = (mode) => {
        let containerAspect = 16 / 9;
        if (containerRef.current) {
            const rect = containerRef.current.getBoundingClientRect();
            if (rect.width && rect.height) {
                containerAspect = rect.width / rect.height;
            }
        } else if (videoDims.width && videoDims.height) {
            containerAspect = videoDims.width / videoDims.height;
        }

        const targetAspect = mode === 'horizontal' ? 16 / 9 : 9 / 16;
        if (mode === 'letterbox') {
            setCropRect(null);
            return;
        }

        // Start with a reasonable size (e.g., 80% width or height)
        let w, h;

        // We use a small epsilon for float comparison
        if (containerAspect > targetAspect + 0.01) {
            // Container is strictly wider than target.
            // Fit by Height.
            h = 60; // 60% of height
            // W% = H% * (Target / Container)
            w = h * (targetAspect / containerAspect);
        } else {
            // Container is narrower or equal (taller)
            // Fit by Width.
            w = 80; // 80% of width
            // H% = W% * (Container / Target)
            h = w * (containerAspect / targetAspect);
        }

        // Center it
        const x = (100 - w) / 2;
        const y = (100 - h) / 2;

        const newRect = { x, y, width: w, height: h };
        setCropRect(newRect);
        updateClipCrop(newRect);
    };

    const handleCropModeChange = (mode) => {
        setCropMode(mode);
        if (mode === 'letterbox') {
            const updated = {
                ...localClip,
                aspect_ratio: '9:16'
            };
            delete updated.crop_x;
            delete updated.crop_y;
            delete updated.crop_width;
            delete updated.crop_height;
            setLocalClip(updated);
            onUpdate(updated);
            setCropRect(null);
        } else {
            // Clear aspect_ratio when switching back to crop
            const updated = { ...localClip };
            delete updated.aspect_ratio;
            setLocalClip(updated);
            initCropRect(mode);
        }
    };

    // Drag and Resize Implementation
    const [resizeHandle, setResizeHandle] = useState(null); // 'nw', 'ne', 'sw', 'se' or null

    const updateClipCrop = (rect) => {
        if (cropMode === 'letterbox') return;
        const dims = getSafeVideoDims();
        if (!dims.width || dims.width <= 16) return;

        // Ensure aspect ratio consistency in output
        const currentAspect = cropMode === 'horizontal' ? 16 / 9 : 9 / 16;

        // Convert percentages to pixels for the video
        let cropW = Math.round((rect.width / 100) * dims.width);
        // Force Height based on Width to ensure strict aspect match (within 1px)
        let cropH = Math.round(cropW / currentAspect);

        // Re-check bounds (if H pushed us out, adjust W instead?) 
        // For simplicity, just clamp loop or trust the rounding.
        if (cropH > dims.height) {
            cropH = dims.height;
            cropW = Math.round(cropH * currentAspect);
        }

        const cropX = Math.round((rect.x / 100) * dims.width);
        const cropY = Math.round((rect.y / 100) * dims.height);

        const updated = {
            ...localClip,
            crop_x: cropX,
            crop_y: cropY,
            crop_width: cropW,
            crop_height: cropH
        };
        setLocalClip(updated);
        onUpdate(updated);
    };

    const onMouseDown = (e, handle = null) => {
        e.preventDefault();
        e.stopPropagation();

        setDragStart({ x: e.clientX, y: e.clientY });
        setRectStart({ ...cropRect });
        if (handle) {
            setResizeHandle(handle);
        } else {
            setIsDragging(true);
        }
    };

    useEffect(() => {
        const onMouseMove = (e) => {
            if (!isDragging && !resizeHandle) return;

            e.preventDefault();

            const rect = containerRef.current.getBoundingClientRect();
            const deltaXPx = e.clientX - dragStart.x;
            const deltaYPx = e.clientY - dragStart.y;

            // Convert pixel delta to percentage delta
            const deltaX = (deltaXPx / rect.width) * 100;
            const deltaY = (deltaYPx / rect.height) * 100;

            if (isDragging) {
                let newX = rectStart.x + deltaX;
                let newY = rectStart.y + deltaY;

                // Constrain to bounds
                newX = Math.max(0, Math.min(100 - cropRect.width, newX));

                newY = Math.max(0, Math.min(100 - cropRect.height, newY));

                setCropRect({ ...cropRect, x: newX, y: newY });
            } else if (resizeHandle) {
                const currentAspect = cropMode === 'horizontal' ? 16 / 9 : 9 / 16;
                const dims = getSafeVideoDims();
                const videoAspect = dims.width && dims.height ? dims.width / dims.height : 16 / 9;

                // Factor to convert Width% change to Height% change to maintain aspect ratio
                // H% = W% * (VideoAspect / TargetAspect)
                const K = videoAspect / currentAspect;

                let newX = rectStart.x;
                let newY = rectStart.y;
                let newW = rectStart.width;
                let newH = rectStart.height;

                // Simple X-axis driven resize (reverted from multi-axis)
                let dW = deltaX;

                // Invert delta for left-side handles
                if (resizeHandle === 'sw' || resizeHandle === 'nw') {
                    dW = -dW;
                }

                newW = rectStart.width + dW;
                newH = newW * K;

                // Min size check relative to video
                // 16px min width seems reasonable
                const minWPercent = (16 / dims.width) * 100;
                if (newW < minWPercent) {
                    newW = minWPercent;
                    newH = newW * K;
                }

                // Apply changes based on handle position
                if (resizeHandle === 'se') {
                    // Top-Left fixed, grow right/down
                } else if (resizeHandle === 'sw') {
                    // Top-Right fixed, grow left/down
                    newX = rectStart.x - (newW - rectStart.width);
                } else if (resizeHandle === 'ne') {
                    // Bottom-Left fixed, grow right/up
                    newY = rectStart.y - (newH - rectStart.height);
                } else if (resizeHandle === 'nw') {
                    // Bottom-Right fixed, grow left/up
                    newX = rectStart.x - (newW - rectStart.width);
                    newY = rectStart.y - (newH - rectStart.height);
                }

                // Bounds checks could go here, but clamping width usually sufficient for drag
                // If X/Y go out of bounds, we might want to clamp them and adjust W/H back?
                // For now, simple clamping of X/Y to valid range (0-100) done in effect loop?
                // Actually we just set them.

                // Basic clamp for position 
                // Note: This doesn't prevent growing off-screen, but prevents moving off-screen.
                // ideally we clamp (newX + newW) <= 100 etc.

                setCropRect({ x: newX, y: newY, width: newW, height: newH });
            }
        };

        const onMouseUp = () => {
            if (isDragging || resizeHandle) {
                setIsDragging(false);
                setResizeHandle(null);
                updateClipCrop(cropRect);
            }
        };

        if (isDragging || resizeHandle) {
            window.addEventListener('mousemove', onMouseMove);
            window.addEventListener('mouseup', onMouseUp);
        }

        return () => {
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
        };
    }, [isDragging, resizeHandle, dragStart, rectStart, cropRect, cropMode, videoDims]);

    const fetchReferenceComments = async () => {
        console.log("fetchReferenceComments videoFilename:", videoFilename);
        if (!videoFilename) {
            alert(`動画ファイル名が見つかりません (videoFilename=${videoFilename})`);
            return;
        }
        setIsFetchingReference(true);
        try {
            const response = await fetch('/youtube/comments/range', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_filename: videoFilename,
                    start: localClip.start,
                    end: localClip.end
                })
            });
            if (!response.ok) throw new Error('コメントの取得に失敗しました');
            const data = await response.json();
            setReferenceComments(data.comments || []);
            setShowReferenceComments(true);
        } catch (e) {
            console.error(e);
            alert(e.message);
        } finally {
            setIsFetchingReference(false);
        }
    };

    const renderStars = (score) => {
        return '⭐️'.repeat(score || 0);
    };

    return (
        <div className="bg-white rounded-lg shadow p-4 mb-4 border border-gray-200">
            <div className="flex flex-col md:flex-row gap-4">
                {/* Video Preview */}
                <div
                    ref={containerRef}
                    className="w-full md:w-1/3 bg-black rounded overflow-hidden relative self-start"
                    style={{
                        // Remove manual aspect ratio, let video define height
                    }}
                >
                    <video
                        ref={videoRef}
                        src={videoUrl}
                        className="w-full h-auto block" // h-auto lets video determine height
                        onTimeUpdate={handleTimeUpdate}
                        onLoadedMetadata={handleLoadedMetadata}
                        onPause={() => setIsPlaying(false)}
                        onPlay={() => setIsPlaying(true)}
                    />

                    {/* Danmaku Overlay */}
                    <DanmakuLayer
                        comments={comments}
                        currentTime={currentTime}
                        enabled={showDanmaku}
                        density={danmakuDensity}
                        videoHeight={videoRef.current?.clientHeight || videoDims.height || 1080}
                        channelId={channelId}
                    />

                    {/* Crop Overlay */}
                    {
                        showCrop && cropMode !== 'letterbox' && cropRect && (
                            <div
                                className="absolute border-2 border-white shadow-[0_0_0_9999px_rgba(0,0,0,0.5)]"
                                style={{
                                    left: `${cropRect.x}%`,
                                    top: `${cropRect.y}%`,
                                    width: `${cropRect.width}%`,
                                    height: `${cropRect.height}%`,
                                }}
                                onMouseDown={(e) => onMouseDown(e)}
                            >
                                {/* Drag Handle (Move) - Full area or specific handle? Full area typically used for move */}
                                <div className="absolute inset-0 cursor-move"></div>

                                {/* Center crosshair */}
                                <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none">
                                    <div className="w-4 h-4 border-t-2 border-l-2 border-white"></div>
                                </div>

                                {/* Resize Handles */}
                                {['nw', 'ne', 'sw', 'se'].map(h => (
                                    <div
                                        key={h}
                                        className={`absolute w-3 h-3 bg-white border border-gray-500 rounded-full z-10
                                        ${h === 'nw' ? '-top-1.5 -left-1.5 cursor-nw-resize' : ''}
                                        ${h === 'ne' ? '-top-1.5 -right-1.5 cursor-ne-resize' : ''}
                                        ${h === 'sw' ? '-bottom-1.5 -left-1.5 cursor-sw-resize' : ''}
                                        ${h === 'se' ? '-bottom-1.5 -right-1.5 cursor-se-resize' : ''}
                                    `}
                                        onMouseDown={(e) => onMouseDown(e, h)}
                                    ></div>
                                ))}
                            </div>
                        )
                    }

                    {/* Time Display */}
                    <div className="absolute top-2 left-2 bg-black bg-opacity-75 text-white px-2 py-1 rounded text-xs font-mono z-10">
                        {formatTime(currentTime)} / {formatTime(localClip.end - localClip.start)}
                    </div>
                    <div className="absolute bottom-2 right-2 flex space-x-2 z-10">
                        {!isPlaying ? (
                            <button
                                onClick={playPreview}
                                className="bg-blue-600 text-white p-1 rounded-full hover:bg-blue-700"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </button>
                        ) : (
                            <button
                                onClick={stopPreview}
                                className="bg-gray-800 text-white p-1 rounded-full hover:bg-gray-700"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </button>
                        )}
                    </div>
                </div >

                {/* Controls */}
                < div className="w-full md:w-2/3 space-y-3" >
                    <div>
                        <label className="block text-sm font-medium text-gray-700">タイトル</label>
                        <input
                            type="text"
                            value={localClip.title}
                            onChange={(e) => handleChange('title', e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2"
                        />
                    </div>

                    {/* Crop Controls */}
                    <div className="bg-gray-50 p-3 rounded border border-gray-200">
                        <div className="flex items-center justify-between mb-2">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={showCrop}
                                    onChange={toggleCrop}
                                    className="rounded text-blue-600 focus:ring-blue-500"
                                />
                                <span className="text-sm font-medium text-gray-700">切り抜き（クロップ）を有効にする</span>
                            </label>
                            {comments && comments.length > 0 && (
                                <label className="flex items-center gap-2 cursor-pointer ml-4">
                                    <input
                                        type="checkbox"
                                        checked={showDanmaku}
                                        onChange={(e) => setShowDanmaku(e.target.checked)}
                                        className="rounded text-blue-600 focus:ring-blue-500"
                                    />
                                    <span className="text-sm font-medium text-gray-700">コメントを表示</span>
                                </label>
                            )}
                        </div>

                        {showCrop && (
                            <div className="flex flex-col gap-2">
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => handleCropModeChange('horizontal')}
                                        className={`flex-1 py-1 px-2 text-sm rounded border ${cropMode === 'horizontal'
                                            ? 'bg-blue-100 border-blue-300 text-blue-700'
                                            : 'bg-white border-gray-300 text-gray-600'
                                            }`}
                                    >
                                        横 (16:9)
                                    </button>
                                    <button
                                        onClick={() => handleCropModeChange('vertical')}
                                        className={`flex-1 py-1 px-2 text-sm rounded border ${cropMode === 'vertical'
                                            ? 'bg-blue-100 border-blue-300 text-blue-700'
                                            : 'bg-white border-gray-300 text-gray-600'
                                            }`}
                                    >
                                        縦 (9:16)
                                    </button>
                                    <button
                                        onClick={() => handleCropModeChange('letterbox')}
                                        className={`flex-1 py-1 px-2 text-sm rounded border ${cropMode === 'letterbox'
                                            ? 'bg-blue-100 border-blue-300 text-blue-700'
                                            : 'bg-white border-gray-300 text-gray-600'
                                            }`}
                                    >
                                        黒枠 (9:16)
                                    </button>
                                </div>
                                <div className="text-xs text-gray-500 text-center">
                                    出力解像度: {localClip.crop_width || 0} x {localClip.crop_height || 0} px
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">開始時間</label>
                            <div className="flex items-center gap-1">
                                <input
                                    type="number"
                                    value={Math.floor(localClip.start / 3600)}
                                    onChange={(e) => {
                                        const hours = parseInt(e.target.value) || 0;
                                        const minutes = Math.floor((localClip.start % 3600) / 60);
                                        const seconds = Math.floor(localClip.start % 60);
                                        handleChange('start', hours * 3600 + minutes * 60 + seconds);
                                    }}
                                    min="0"
                                    className="w-14 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm border p-1.5"
                                    placeholder="0"
                                />
                                <span className="text-xs text-gray-600">:</span>
                                <input
                                    type="number"
                                    value={Math.floor((localClip.start % 3600) / 60)}
                                    onChange={(e) => {
                                        const hours = Math.floor(localClip.start / 3600);
                                        const minutes = parseInt(e.target.value) || 0;
                                        const seconds = Math.floor(localClip.start % 60);
                                        handleChange('start', hours * 3600 + minutes * 60 + seconds);
                                    }}
                                    min="0"
                                    max="59"
                                    className="w-14 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm border p-1.5"
                                    placeholder="0"
                                />
                                <span className="text-xs text-gray-600">:</span>
                                <input
                                    type="number"
                                    value={Math.floor(localClip.start % 60)}
                                    onChange={(e) => {
                                        const hours = Math.floor(localClip.start / 3600);
                                        const minutes = Math.floor((localClip.start % 3600) / 60);
                                        const seconds = parseInt(e.target.value) || 0;
                                        handleChange('start', hours * 3600 + minutes * 60 + Math.min(59, seconds));
                                    }}
                                    min="0"
                                    max="59"
                                    className="w-14 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm border p-1.5"
                                    placeholder="0"
                                />
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5">{localClip.start.toFixed(1)}秒</div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">終了時間</label>
                            <div className="flex items-center gap-1">
                                <input
                                    type="number"
                                    value={Math.floor(localClip.end / 3600)}
                                    onChange={(e) => {
                                        const hours = parseInt(e.target.value) || 0;
                                        const minutes = Math.floor((localClip.end % 3600) / 60);
                                        const seconds = Math.floor(localClip.end % 60);
                                        handleChange('end', hours * 3600 + minutes * 60 + seconds);
                                    }}
                                    min="0"
                                    className="w-14 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm border p-1.5"
                                    placeholder="0"
                                />
                                <span className="text-xs text-gray-600">:</span>
                                <input
                                    type="number"
                                    value={Math.floor((localClip.end % 3600) / 60)}
                                    onChange={(e) => {
                                        const hours = Math.floor(localClip.end / 3600);
                                        const minutes = parseInt(e.target.value) || 0;
                                        const seconds = Math.floor(localClip.end % 60);
                                        handleChange('end', hours * 3600 + minutes * 60 + seconds);
                                    }}
                                    min="0"
                                    max="59"
                                    className="w-14 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm border p-1.5"
                                    placeholder="0"
                                />
                                <span className="text-xs text-gray-600">:</span>
                                <input
                                    type="number"
                                    value={Math.floor(localClip.end % 60)}
                                    onChange={(e) => {
                                        const hours = Math.floor(localClip.end / 3600);
                                        const minutes = Math.floor((localClip.end % 3600) / 60);
                                        const seconds = parseInt(e.target.value) || 0;
                                        handleChange('end', hours * 3600 + minutes * 60 + Math.min(59, seconds));
                                    }}
                                    min="0"
                                    max="59"
                                    className="w-14 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm border p-1.5"
                                    placeholder="0"
                                />
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5">{localClip.end.toFixed(1)}秒</div>
                        </div>
                    </div>

                    <div className="text-sm text-gray-500">
                        <p>理由: {localClip.reason || "手動追加"}</p>
                        <p>長さ: {(localClip.end - localClip.start).toFixed(1)}秒</p>
                    </div>

                    {/* AI Evaluation Section */}
                    {
                        localClip.evaluation_score && (
                            <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mt-2">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-sm font-medium text-gray-700">AIオススメ度:</span>
                                    <span className="text-lg">{renderStars(localClip.evaluation_score)}</span>
                                </div>
                                <p className="text-xs text-gray-600">{localClip.evaluation_reason}</p>
                            </div>
                        )
                    }

                    {/* Comment Count Section */}
                    {
                        localClip.comment_count !== undefined && (
                            <div className="bg-blue-50 border border-blue-200 rounded p-3 mt-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-lg">💬</span>
                                    <span className="text-sm font-medium text-gray-700">コメント数:</span>
                                    <span className="text-lg font-bold text-blue-700">{localClip.comment_count}</span>
                                    <span className="text-sm text-gray-600 ml-2">
                                        ({localClip.comments_per_minute !== undefined ? localClip.comments_per_minute : ((localClip.comment_count / (localClip.end - localClip.start)) * 60).toFixed(1)}/分)
                                    </span>
                                </div>
                            </div>
                        )
                    }

                    {/* Reference Comments Display */}
                    <div className="mt-2 text-right">
                        <button
                            onClick={fetchReferenceComments}
                            disabled={isFetchingReference}
                            className="text-xs text-blue-600 hover:text-blue-800 underline"
                        >
                            {isFetchingReference ? '読み込み中...' : 'この区間のコメントを参考資料として表示'}
                        </button>
                    </div>

                    {showReferenceComments && (
                        <div className="mt-2 border border-gray-200 rounded-md bg-white p-2">
                            <div className="flex justify-between items-center mb-2 border-b pb-1">
                                <span className="text-xs font-bold text-gray-700">参考コメント一覧 ({referenceComments.length}件)</span>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => {
                                            const text = referenceComments.map(c => {
                                                const relTime = Math.max(0, c.timestamp - localClip.start);
                                                return `[${formatTime(relTime)}] ${c.text}`;
                                            }).join('\n');

                                            // Clipboard API (secure contexts)
                                            if (navigator.clipboard && navigator.clipboard.writeText) {
                                                navigator.clipboard.writeText(text).then(() => {
                                                    alert('コピーしました');
                                                }).catch(err => {
                                                    console.warn('Clipboard API failed, trying fallback', err);
                                                    fallbackCopyTextToClipboard(text);
                                                });
                                            } else {
                                                // Fallback for non-secure contexts
                                                fallbackCopyTextToClipboard(text);
                                            }

                                            function fallbackCopyTextToClipboard(text) {
                                                var textArea = document.createElement("textarea");
                                                textArea.value = text;

                                                // Avoid scrolling to bottom
                                                textArea.style.top = "0";
                                                textArea.style.left = "0";
                                                textArea.style.position = "fixed";
                                                textArea.style.opacity = "0";

                                                document.body.appendChild(textArea);
                                                textArea.focus();
                                                textArea.select();

                                                try {
                                                    var successful = document.execCommand('copy');
                                                    if (successful) {
                                                        alert('コピーしました');
                                                    } else {
                                                        alert('コピーに失敗しました');
                                                    }
                                                } catch (err) {
                                                    console.error('Fallback: Oops, unable to copy', err);
                                                    alert('コピーに失敗しました');
                                                }

                                                document.body.removeChild(textArea);
                                            }
                                        }}
                                        className="text-xs text-blue-600 hover:text-blue-800"
                                    >
                                        全体をコピー
                                    </button>
                                    <button onClick={() => setShowReferenceComments(false)} className="text-xs text-gray-400 hover:text-gray-600">閉じる</button>
                                </div>
                            </div>
                            <div className="max-h-48 overflow-y-auto text-xs space-y-1">
                                {referenceComments.length === 0 ? (
                                    <p className="text-gray-400 italic">該当するコメントはありません</p>
                                ) : (
                                    referenceComments.map((c, i) => (
                                        <div key={i} className="flex gap-2 hover:bg-gray-50 p-1 rounded">
                                            <span className="text-gray-400 font-mono w-12 shrink-0 text-right">
                                                {formatTime(Math.max(0, c.timestamp - localClip.start))}
                                            </span>
                                            <span className="text-gray-800 break-words">{c.text}</span>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    )}

                    <div className="flex justify-end space-x-3 pt-2">
                        <button
                            onClick={() => onDelete(clip.id)}
                            className="px-3 py-1.5 border border-red-300 text-red-700 rounded hover:bg-red-50 text-sm"
                        >
                            削除
                        </button>
                        <button
                            onClick={() => onCreate({
                                ...localClip,
                                with_danmaku: showDanmaku,
                                danmaku_density: danmakuDensity
                            })}
                            disabled={isCreating}
                            className={`px-3 py-1.5 text-white rounded text-sm font-medium ${isCreating
                                ? 'bg-green-400 cursor-not-allowed'
                                : 'bg-green-600 hover:bg-green-700'
                                }`}
                        >
                            {isCreating ? (
                                <span className="flex items-center">
                                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    作成中...
                                </span>
                            ) : (
                                'このクリップを作成'
                            )}
                        </button>
                    </div>
                </div >
            </div >
        </div >
    );
}

export default ClipPreview;

