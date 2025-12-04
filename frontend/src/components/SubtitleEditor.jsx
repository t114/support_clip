import React, { useEffect, useRef } from 'react';
import { generateUUID } from '../utils/vtt';

export default function SubtitleEditor({ subtitles, onSubtitlesChange, currentTime, onSeek, onPause, savedStyles }) {
    const activeIndex = subtitles.findIndex(
        sub => currentTime >= sub.start && currentTime <= sub.end
    );

    const itemRefs = useRef({});
    const listRef = useRef(null);

    useEffect(() => {
        // Don't scroll if the user is currently editing (focus is ANYWHERE inside the list)
        const isEditing = listRef.current?.contains(document.activeElement);

        if (activeIndex !== -1 && itemRefs.current[activeIndex] && !isEditing) {
            itemRefs.current[activeIndex].scrollIntoView({
                behavior: 'smooth',
                block: 'nearest', // Changed to nearest to avoid large jumps
            });
        }
    }, [activeIndex]);

    const handleFocus = (startTime) => {
        // Add a small epsilon to ensure we land inside the subtitle time range
        // and avoid floating point issues where currentTime < startTime
        onSeek(startTime + 0.01);
        if (onPause) onPause();
    };

    const handleChange = (index, field, value) => {
        const newSubtitles = [...subtitles];
        newSubtitles[index] = { ...newSubtitles[index], [field]: value };
        onSubtitlesChange(newSubtitles);
    };

    const handleAdd = (index) => {
        const currentSub = subtitles[index];
        const newStart = currentSub ? currentSub.end : 0;
        const newEnd = newStart + 2; // Default 2 seconds duration

        const newSub = {
            id: generateUUID(),
            start: newStart,
            end: newEnd,
            text: ''
        };

        const newSubtitles = [...subtitles];
        newSubtitles.splice(index + 1, 0, newSub);
        onSubtitlesChange(newSubtitles);
    };

    const handleDelete = (index) => {
        if (confirm('この字幕を削除してもよろしいですか？')) {
            const newSubtitles = subtitles.filter((_, i) => i !== index);
            onSubtitlesChange(newSubtitles);
        }
    };

    const formatTimeInput = (seconds) => {
        return new Date(seconds * 1000).toISOString().substr(11, 12);
    };

    const parseTimeInput = (timeString) => {
        const [h, m, s] = timeString.split(':').map(Number);
        return h * 3600 + m * 60 + s;
    };

    return (
        <div className="bg-white rounded-lg shadow flex flex-col h-[600px]">
            <div className="p-4 border-b flex justify-between items-center">
                <h3 className="font-bold text-gray-700">字幕編集</h3>
                <button
                    onClick={() => handleAdd(subtitles.length - 1)}
                    className="text-sm bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
                >
                    ＋ 最後に追加
                </button>
            </div>
            <div
                ref={listRef}
                className="flex-1 overflow-y-auto p-4 space-y-4"
            >
                {subtitles.map((sub, index) => (
                    <div
                        key={sub.id}
                        ref={el => itemRefs.current[index] = el}
                        className={`p-3 rounded border transition-colors relative group ${index === activeIndex ? 'bg-blue-50 border-blue-500 ring-1 ring-blue-500' : 'border-gray-200 hover:border-gray-300'
                            }`}
                        onClick={() => handleFocus(sub.start)}
                    >
                        <div className="flex space-x-2 mb-2">
                            <div className="flex-1">
                                <label className="block text-xs text-gray-500">開始</label>
                                <input
                                    type="text"
                                    defaultValue={formatTimeInput(sub.start)}
                                    onBlur={(e) => handleChange(index, 'start', parseTimeInput(e.target.value))}
                                    onFocus={() => handleFocus(sub.start)}
                                    className="w-full text-sm border rounded px-1"
                                />
                            </div>
                            <div className="flex-1">
                                <label className="block text-xs text-gray-500">終了</label>
                                <input
                                    type="text"
                                    defaultValue={formatTimeInput(sub.end)}
                                    onBlur={(e) => handleChange(index, 'end', parseTimeInput(e.target.value))}
                                    onFocus={() => handleFocus(sub.start)}
                                    className="w-full text-sm border rounded px-1"
                                />
                            </div>
                        </div>
                        <textarea
                            value={sub.text}
                            onChange={(e) => handleChange(index, 'text', e.target.value)}
                            onFocus={() => handleFocus(sub.start)}
                            className="w-full text-sm border rounded p-2 min-h-[60px]"
                        />

                        {/* Action Buttons */}
                        <div className="absolute top-2 right-2 flex space-x-1 opacity-0 group-hover:opacity-100 transition-opacity items-center">
                            {/* Style Selector */}
                            {savedStyles && Object.keys(savedStyles).length > 0 && (
                                <select
                                    value={sub.styleName || ''}
                                    onChange={(e) => handleChange(index, 'styleName', e.target.value)}
                                    onClick={(e) => e.stopPropagation()}
                                    className="text-xs border border-gray-300 rounded px-1 py-0.5 mr-2 max-w-[100px]"
                                >
                                    <option value="">デフォルト</option>
                                    {Object.keys(savedStyles).map(name => (
                                        <option key={name} value={name}>{name}</option>
                                    ))}
                                </select>
                            )}

                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleAdd(index);
                                }}
                                className="p-1 bg-green-100 text-green-600 rounded hover:bg-green-200"
                                title="下に挿入"
                            >
                                ＋
                            </button>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleDelete(index);
                                }}
                                className="p-1 bg-red-100 text-red-600 rounded hover:bg-red-200"
                                title="削除"
                            >
                                🗑️
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
