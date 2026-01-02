
import React, { useState, useEffect, useRef } from 'react';

export default function DescriptionModal({ isOpen, onClose, initialDescription, detectedMembers, allMembers = [] }) {
    const [description, setDescription] = useState(initialDescription || '');
    const [copied, setCopied] = useState(false);
    const [displayedMembers, setDisplayedMembers] = useState(detectedMembers || []);
    const [isMemberSelectorOpen, setIsMemberSelectorOpen] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');

    // Update state when initial props change (e.g. opening modal)
    useEffect(() => {
        setDescription(initialDescription || '');
        setDisplayedMembers(detectedMembers || []);
        setCopied(false);
    }, [initialDescription, detectedMembers]);

    const handleCopy = async () => {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(description);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            } else {
                const textArea = document.createElement('textarea');
                textArea.value = description;
                document.body.appendChild(textArea);
                textArea.select();
                try {
                    document.execCommand('copy');
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                } catch (err) {
                    console.error('Fallback copy failed:', err);
                    alert('コピーに失敗しました。');
                } finally {
                    document.body.removeChild(textArea);
                }
            }
        } catch (err) {
            console.error('Failed to copy text:', err);
            alert('コピーに失敗しました。');
        }
    };

    const handleAddMember = (member) => {
        // Prevent duplicates
        if (displayedMembers.some(m => m.name_ja === member.name_ja)) {
            alert('このメンバーは既に追加されています');
            return;
        }

        const newMembers = [...displayedMembers, member];
        setDisplayedMembers(newMembers);

        // Update Description Text
        let newDesc = description;

        // 1. Add to "出演" section
        const memberInfo = `　${member.name_ja} / ${member.name_en}\n　${member.channel_url}`;

        if (newDesc.includes('■ 出演')) {
            // Find end of "出演" section (next ■ or end of string)
            const parts = newDesc.split('■ 出演');
            const afterHeader = parts[1];

            // Find where the next section starts
            const nextSectionIndex = afterHeader.indexOf('\n■');

            if (nextSectionIndex !== -1) {
                // Insert before next section
                const sectionContent = afterHeader.substring(0, nextSectionIndex);
                if (!sectionContent.endsWith('\n')) {
                    // unexpected formatting, just append
                    newDesc = parts[0] + '■ 出演' + afterHeader.substring(0, nextSectionIndex) + (afterHeader.substring(0, nextSectionIndex).endsWith('\n') ? '' : '\n') + memberInfo + '\n' + afterHeader.substring(nextSectionIndex);
                } else {
                    newDesc = parts[0] + '■ 出演' + sectionContent + memberInfo + '\n' + afterHeader.substring(nextSectionIndex);
                }
            } else {
                // End of text
                newDesc = newDesc.trimEnd() + '\n' + memberInfo + '\n';
            }

        } else {
            // Need to create "出演" section. Try to put it after "元動画"
            if (newDesc.includes('■ 元動画')) {
                const parts = newDesc.split('■ 元動画');
                const afterHeader = parts[1];
                const nextSectionIndex = afterHeader.indexOf('\n━━━━━━━━━━━━━━━━'); // Usually end of source section

                if (nextSectionIndex !== -1) {
                    // The source section usually ends with a separator line.
                    // We want to insert AFTER that separator.
                    // Find the end of that separator.
                    const rest = afterHeader.substring(nextSectionIndex + 1); // skip \n
                    const endOfSep = rest.indexOf('\n'); // end of ━━━

                    if (endOfSep !== -1) {
                        const insertPoint = parts[0].length + '■ 元動画'.length + nextSectionIndex + 1 + endOfSep + 1;
                        newDesc = newDesc.slice(0, insertPoint) + '\n■ 出演\n' + memberInfo + '\n' + newDesc.slice(insertPoint);
                    } else {
                        // Fallback
                        newDesc += '\n\n■ 出演\n' + memberInfo + '\n';
                    }
                } else {
                    newDesc += '\n\n■ 出演\n' + memberInfo + '\n';
                }
            } else {
                newDesc = '■ 出演\n' + memberInfo + '\n\n' + newDesc;
            }
        }

        // 2. Add tag
        if (newDesc.includes('■ タグ')) {
            const tag = `#${member.name_ja}`;
            // Find the end of the description or next section
            // Actually, tags are usually at the end line like "　#tag #tag"
            // Just append to the end of the line that contains existing tags?
            // Or append to the list of tags.
            // Simplest: Find "■ タグ" and append the tag to the end of that section's line.

            // Let's just Regex replace to be safe?
            // Or just append it to the end of lines starting with space after "■ タグ"

            // Implementation detail: backend puts tags on one line: "　#tag1 #tag2..."
            const tagIndex = newDesc.indexOf('■ タグ');
            const nextLineIndex = newDesc.indexOf('\n', tagIndex);
            if (nextLineIndex !== -1) {
                // The line after "■ タグ" usually contains the tags
                const tagLineStart = nextLineIndex + 1;
                const tagLineEnd = newDesc.indexOf('\n', tagLineStart);

                if (tagLineEnd !== -1) {
                    const currentTags = newDesc.substring(tagLineStart, tagLineEnd);
                    if (!currentTags.includes(tag)) {
                        newDesc = newDesc.substring(0, tagLineEnd) + ' ' + tag + newDesc.substring(tagLineEnd);
                    }
                } else {
                    // Last line
                    newDesc += ' ' + tag;
                }
            }
        }

        setDescription(newDesc);
        setIsMemberSelectorOpen(false); // Close selector after adding
    };

    // Filter members for search
    const filteredMembers = allMembers.filter(m =>
        m.name_ja.includes(searchTerm) ||
        m.name_en.toLowerCase().includes(searchTerm.toLowerCase()) ||
        m.keywords.some(k => k.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            {/* Backdrop */}
            <div className="fixed inset-0 bg-black bg-opacity-50 transition-opacity" onClick={onClose}></div>

            {/* Modal */}
            <div className="flex items-center justify-center min-h-screen p-4">
                <div className="relative bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] flex flex-col">
                    {/* Header */}
                    <div className="flex items-center justify-between p-6 border-b">
                        <h2 className="text-2xl font-bold text-gray-900">動画概要欄</h2>
                        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl">✕</button>
                    </div>

                    {/* Detected Members & Add Button */}
                    <div className="px-6 py-4 bg-blue-50 border-b">
                        <div className="flex justify-between items-center mb-2">
                            <h3 className="text-sm font-semibold text-blue-900">出演メンバー:</h3>
                            <button
                                onClick={() => setIsMemberSelectorOpen(true)}
                                className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 transition-colors"
                            >
                                + メンバーを追加
                            </button>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            {displayedMembers.length > 0 ? (
                                displayedMembers.map((member, index) => (
                                    <span key={index} className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800">
                                        {member.name_ja}
                                    </span>
                                ))
                            ) : (
                                <span className="text-sm text-gray-500">メンバーが検出されませんでした</span>
                            )}
                        </div>
                    </div>

                    {/* Member Selector Modal (Overlay) */}
                    {isMemberSelectorOpen && (
                        <div className="absolute inset-0 z-10 bg-black bg-opacity-50 flex items-center justify-center p-4">
                            <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
                                <div className="p-4 border-b flex justify-between items-center">
                                    <h3 className="font-bold text-lg">メンバーを選択</h3>
                                    <button onClick={() => setIsMemberSelectorOpen(false)} className="text-gray-500 hover:text-gray-700">✕</button>
                                </div>
                                <div className="p-4 border-b">
                                    <input
                                        type="text"
                                        placeholder="名前で検索..."
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                        className="w-full p-2 border rounded"
                                        autoFocus
                                    />
                                </div>
                                <div className="flex-1 overflow-y-auto p-2">
                                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                        {filteredMembers.map((member, idx) => {
                                            const isSelected = displayedMembers.some(m => m.name_ja === member.name_ja);
                                            return (
                                                <button
                                                    key={idx}
                                                    onClick={() => !isSelected && handleAddMember(member)}
                                                    disabled={isSelected}
                                                    className={`text-left p-3 rounded border flex items-center gap-2 ${isSelected
                                                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                                            : 'hover:bg-blue-50 cursor-pointer border-gray-200'
                                                        }`}
                                                >
                                                    <span className={`w-4 h-4 border rounded flex items-center justify-center ${isSelected ? 'bg-blue-500 border-blue-500' : 'border-gray-400'}`}>
                                                        {isSelected && <span className="text-white text-xs">✓</span>}
                                                    </span>
                                                    <div className="flex flex-col overflow-hidden">
                                                        <span className="text-sm font-bold truncate">{member.name_ja}</span>
                                                        <span className="text-xs text-gray-500 truncate">{member.generation}</span>
                                                    </div>
                                                </button>
                                            );
                                        })}
                                        {filteredMembers.length === 0 && (
                                            <div className="col-span-full text-center py-8 text-gray-500">
                                                見つかりませんでした
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Description Editor */}
                    <div className="flex-1 p-6 overflow-y-auto">
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="w-full h-full min-h-[400px] p-4 border border-gray-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                        />
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between p-6 border-t bg-gray-50">
                        <div className="text-sm text-gray-600">
                            {description.length} 文字
                        </div>
                        <div className="flex space-x-3">
                            <button onClick={onClose} className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100">
                                閉じる
                            </button>
                            <button
                                onClick={handleCopy}
                                className={`px-6 py-2 rounded-lg transition-colors ${copied ? 'bg-green-600 text-white' : 'bg-blue-600 text-white hover:bg-blue-700'}`}
                            >
                                {copied ? '✓ コピー完了' : 'コピー'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
