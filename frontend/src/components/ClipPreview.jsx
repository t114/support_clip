import React, { useState, useRef, useEffect } from 'react';

function ClipPreview({ clip, videoUrl, onUpdate, onDelete, onCreate, isCreating }) {
    const videoRef = useRef(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [localClip, setLocalClip] = useState(clip);
    const [currentTime, setCurrentTime] = useState(0);

    useEffect(() => {
        setLocalClip(clip);
    }, [clip]);

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

    const renderStars = (score) => {
        return '⭐️'.repeat(score || 0);
    };

    return (
        <div className="bg-white rounded-lg shadow p-4 mb-4 border border-gray-200">
            <div className="flex flex-col md:flex-row gap-4">
                {/* Video Preview */}
                <div className="w-full md:w-1/3 bg-black rounded overflow-hidden relative aspect-video">
                    <video
                        ref={videoRef}
                        src={videoUrl}
                        className="w-full h-full object-contain"
                        onTimeUpdate={handleTimeUpdate}
                        onPause={() => setIsPlaying(false)}
                        onPlay={() => setIsPlaying(true)}
                    />
                    {/* Time Display */}
                    <div className="absolute top-2 left-2 bg-black bg-opacity-75 text-white px-2 py-1 rounded text-xs font-mono">
                        {formatTime(currentTime)} / {formatTime(localClip.end - localClip.start)}
                    </div>
                    <div className="absolute bottom-2 right-2 flex space-x-2">
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
                </div>

                {/* Controls */}
                <div className="w-full md:w-2/3 space-y-3">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">タイトル</label>
                        <input
                            type="text"
                            value={localClip.title}
                            onChange={(e) => handleChange('title', e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2"
                        />
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
                    {localClip.evaluation_score && (
                        <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mt-2">
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium text-gray-700">AIオススメ度:</span>
                                <span className="text-lg">{renderStars(localClip.evaluation_score)}</span>
                            </div>
                            <p className="text-xs text-gray-600">{localClip.evaluation_reason}</p>
                        </div>
                    )}

                    {/* Comment Count Section */}
                    {localClip.comment_count !== undefined && (
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
                    )}

                    <div className="flex justify-end space-x-3 pt-2">
                        <button
                            onClick={() => onDelete(clip.id)}
                            className="px-3 py-1.5 border border-red-300 text-red-700 rounded hover:bg-red-50 text-sm"
                        >
                            削除
                        </button>
                        <button
                            onClick={() => onCreate(localClip)}
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
                </div>
            </div>
        </div>
    );
}

export default ClipPreview;
