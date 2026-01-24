import React, { useEffect, useRef, useState } from 'react';
import { generateUUID } from '../utils/vtt';

// Searchable Style Dropdown Component
function StyleDropdown({ savedStyles, currentStyle, onStyleChange, recentStyleNames, onStyleUsed, isOpen, onToggle, onClose }) {
    const [searchTerm, setSearchTerm] = useState('');
    const dropdownRef = useRef(null);

    // Filter styles based on search term
    const filteredStyles = Object.keys(savedStyles).filter(name =>
        name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Get recent styles that actually still exist
    const validRecentStyles = (recentStyleNames || []).filter(name => savedStyles[name]);

    // Close dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                onClose();
                setSearchTerm('');
            }
        }

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [isOpen, onClose]);

    const handleStyleSelect = (styleName) => {
        onStyleChange(styleName);
        if (styleName) onStyleUsed(styleName);
        onClose();
        setSearchTerm('');
    };

    return (
        <div ref={dropdownRef} className="relative" onClick={(e) => e.stopPropagation()}>
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onToggle();
                }}
                className="text-xs border border-gray-300 rounded px-2 py-1 bg-white hover:bg-gray-50 max-w-[120px] truncate"
                title={currentStyle || 'デフォルト'}
            >
                {currentStyle || 'デフォルト'}
            </button>

            {isOpen && (
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-300 rounded shadow-lg z-50 w-64">
                    <div className="p-2 border-b">
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            placeholder="スタイルを検索..."
                            className="w-full text-xs border border-gray-300 rounded px-2 py-1"
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                        />
                    </div>
                    <div className="max-h-60 overflow-y-auto">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                handleStyleSelect('');
                            }}
                            className={`w-full text-left px-3 py-2 text-xs hover:bg-blue-50 ${!currentStyle ? 'bg-blue-100 font-semibold' : ''
                                }`}
                        >
                            デフォルト
                        </button>

                        {/* Recent Styles Section */}
                        {!searchTerm && validRecentStyles.length > 0 && (
                            <div className="border-t border-b bg-gray-50">
                                <div className="px-3 py-1 text-[10px] font-bold text-gray-400 uppercase tracking-wider">最近使用したスタイル</div>
                                {validRecentStyles.map(name => (
                                    <button
                                        key={`recent-${name}`}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleStyleSelect(name);
                                        }}
                                        className={`w-full text-left px-3 py-2 text-xs hover:bg-blue-50 ${currentStyle === name ? 'bg-blue-100 font-semibold' : ''
                                            }`}
                                    >
                                        {name}
                                    </button>
                                ))}
                            </div>
                        )}

                        {filteredStyles.length > 0 ? (
                            <>
                                {!searchTerm && <div className="px-3 py-1 text-[10px] font-bold text-gray-400 uppercase tracking-wider border-b">すべてのスタイル</div>}
                                {filteredStyles.map(name => (
                                    <button
                                        key={name}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleStyleSelect(name);
                                        }}
                                        className={`w-full text-left px-3 py-2 text-xs hover:bg-blue-50 ${currentStyle === name ? 'bg-blue-100 font-semibold' : ''
                                            }`}
                                    >
                                        {name}
                                    </button>
                                ))}
                            </>
                        ) : (
                            <div className="px-3 py-2 text-xs text-gray-500 italic">
                                スタイルが見つかりません
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default function SubtitleEditor({ subtitles, onSubtitlesChange, currentTime, onSeek, onPause, savedStyles, recentStyleNames, onStyleUsed, sounds }) {
    const activeIndex = subtitles.findIndex(
        sub => currentTime >= sub.start && currentTime <= sub.end
    );

    const itemRefs = useRef({});
    const listRef = useRef(null);
    const [styleSearchTerm, setStyleSearchTerm] = useState('');
    const [openStyleDropdown, setOpenStyleDropdown] = useState(null);
    const [maxChars, setMaxChars] = useState(15);
    const [autoWrap, setAutoWrap] = useState(false);
    const [findText, setFindText] = useState('');
    const [replaceText, setReplaceText] = useState('');
    const [showBulkReplace, setShowBulkReplace] = useState(false);
    const lastTimeRef = useRef(0);

    // Automatic SE playback during preview
    useEffect(() => {
        const diff = currentTime - lastTimeRef.current;
        // Only play if we are moving forward at a normal pace (avoids playing multiple sounds when seeking)
        if (diff > 0 && diff < 0.5) {
            subtitles.forEach(sub => {
                if (sub.sound && lastTimeRef.current < sub.start && currentTime >= sub.start) {
                    const s = sounds.find(x => x.name === sub.sound);
                    if (s) {
                        const audio = new Audio(s.url);
                        audio.volume = sub.soundVolume !== undefined ? sub.soundVolume : 0.5;
                        audio.play().catch(err => console.error("SE Playback error:", err));
                    }
                }
            });
        }
        lastTimeRef.current = currentTime;
    }, [currentTime, subtitles, sounds]);

    // Helper to wrap text based on character count
    const wrapText = (text, limit) => {
        if (!text || limit <= 0) return text;

        // Remove existing manual line breaks first to re-wrap properly
        const cleanText = text.replace(/\n/g, '');
        const lines = [];
        for (let i = 0; i < cleanText.length; i += limit) {
            lines.push(cleanText.substring(i, i + limit));
        }
        return lines.join('\n');
    };

    const handleApplyAutoWrap = () => {
        const newSubtitles = subtitles.map(sub => ({
            ...sub,
            text: wrapText(sub.text, maxChars)
        }));
        onSubtitlesChange(newSubtitles);
    };

    const handleBulkReplace = () => {
        if (!findText) return;
        let count = 0;
        const newSubtitles = subtitles.map(sub => {
            if (sub.text && sub.text.includes(findText)) {
                const newText = sub.text.split(findText).join(replaceText);
                if (newText !== sub.text) {
                    count++;
                    return { ...sub, text: newText };
                }
            }
            return sub;
        });

        if (count > 0) {
            onSubtitlesChange(newSubtitles);
            alert(`${count}箇所の字幕を置換しました`);
        } else {
            alert('置換対象が見つかりませんでした');
        }
    };

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
        let finalValue = value;
        if (field === 'text' && autoWrap) {
            finalValue = wrapText(value, maxChars);
        }

        const newSubtitles = [...subtitles];
        newSubtitles[index] = { ...newSubtitles[index], [field]: finalValue };
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
            <div className="p-4 border-b flex flex-col space-y-3">
                <div className="flex justify-between items-center">
                    <div className="flex items-center space-x-2">
                        <h3 className="font-bold text-gray-700">字幕編集</h3>
                        <button
                            onClick={() => setShowBulkReplace(!showBulkReplace)}
                            className={`p-1 rounded transition-colors ${showBulkReplace ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
                            title={showBulkReplace ? "一括置換を隠す" : "一括置換を表示"}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </button>
                    </div>
                    <button
                        onClick={() => handleAdd(subtitles.length - 1)}
                        className="text-sm bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
                    >
                        ＋ 最後に追加
                    </button>
                </div>

                {/* Auto Line Break Settings */}
                <div className="flex items-center space-x-4 bg-gray-50 p-2 rounded border border-gray-100">
                    <div className="flex items-center space-x-2">
                        <label className="text-xs font-medium text-gray-600">自動改行:</label>
                        <input
                            type="number"
                            value={maxChars}
                            onChange={(e) => setMaxChars(Math.max(1, parseInt(e.target.value) || 1))}
                            className="w-12 text-xs border rounded px-1 py-0.5"
                            min="1"
                        />
                        <span className="text-xs text-gray-500">文字</span>
                    </div>
                    <label className="flex items-center space-x-1 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={autoWrap}
                            onChange={(e) => setAutoWrap(e.target.checked)}
                            className="rounded text-blue-500"
                        />
                        <span className="text-xs text-gray-600">入力時に適用</span>
                    </label>
                    <button
                        onClick={handleApplyAutoWrap}
                        className="text-xs bg-gray-200 hover:bg-gray-300 text-gray-700 px-2 py-0.5 rounded transition-colors"
                        title="現在の全字幕に指定文字数で改行を入れます"
                    >
                        全字幕に適用
                    </button>
                </div>

                {/* Bulk Replace Settings */}
                {/* Bulk Replace Settings */}
                {showBulkReplace && (
                    <div className="flex items-center space-x-4 bg-gray-50 p-2 rounded border border-gray-100">
                        <label className="text-xs font-medium text-gray-600">一括置換:</label>
                        <div className="flex items-center space-x-2">
                            <input
                                type="text"
                                value={findText}
                                onChange={(e) => setFindText(e.target.value)}
                                placeholder="検索"
                                className="w-24 text-xs border rounded px-1 py-0.5"
                            />
                            <span className="text-gray-400 text-xs">→</span>
                            <input
                                type="text"
                                value={replaceText}
                                onChange={(e) => setReplaceText(e.target.value)}
                                placeholder="置換"
                                className="w-24 text-xs border rounded px-1 py-0.5"
                            />
                            <button
                                onClick={handleBulkReplace}
                                disabled={!findText}
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${!findText
                                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                    : 'bg-blue-100 hover:bg-blue-200 text-blue-700'
                                    }`}
                            >
                                実行
                            </button>
                        </div>
                    </div>
                )}
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
                        <div className={`absolute top-2 right-2 flex space-x-1 transition-opacity items-center ${index === activeIndex ? 'opacity-100' : 'opacity-40 hover:opacity-100 group-hover:opacity-100'
                            }`}>
                            {/* Sound Selector */}
                            <div className="flex items-center bg-gray-50 border rounded px-1.5 py-0.5 space-x-1">
                                <span className="text-[10px] text-gray-400">🔊</span>
                                <select
                                    value={sub.sound || ''}
                                    onChange={(e) => handleChange(index, 'sound', e.target.value)}
                                    className="text-[10px] bg-transparent border-none outline-none focus:ring-0 max-w-[80px]"
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    <option value="">SEなし</option>
                                    {sounds.map(s => (
                                        <option key={s.name} value={s.name}>{s.name}</option>
                                    ))}
                                </select>
                                {sub.sound && (
                                    <>
                                        <input
                                            type="range"
                                            min="0"
                                            max="1"
                                            step="0.05"
                                            value={sub.soundVolume !== undefined ? sub.soundVolume : 0.5}
                                            onChange={(e) => handleChange(index, 'soundVolume', parseFloat(e.target.value))}
                                            className="w-12 h-1 accent-blue-500 cursor-pointer"
                                            title={`音量: ${Math.round((sub.soundVolume !== undefined ? sub.soundVolume : 0.5) * 100)}%`}
                                            onClick={(e) => e.stopPropagation()}
                                        />
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                const s = sounds.find(x => x.name === sub.sound);
                                                if (s) {
                                                    const audio = new Audio(s.url);
                                                    audio.volume = sub.soundVolume !== undefined ? sub.soundVolume : 0.5;
                                                    audio.play();
                                                }
                                            }}
                                            className="text-[10px] hover:scale-110 transition-transform"
                                            title="プレビュー"
                                        >
                                            ▶️
                                        </button>
                                    </>
                                )}
                            </div>

                            {/* Style Selector */}
                            {savedStyles && Object.keys(savedStyles).length > 0 && (
                                <StyleDropdown
                                    savedStyles={savedStyles}
                                    currentStyle={sub.styleName || ''}
                                    onStyleChange={(styleName) => handleChange(index, 'styleName', styleName)}
                                    recentStyleNames={recentStyleNames}
                                    onStyleUsed={onStyleUsed}
                                    isOpen={openStyleDropdown === index}
                                    onToggle={() => setOpenStyleDropdown(openStyleDropdown === index ? null : index)}
                                    onClose={() => setOpenStyleDropdown(null)}
                                />
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
