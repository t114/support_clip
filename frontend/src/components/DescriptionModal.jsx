import React, { useState } from 'react';

export default function DescriptionModal({ isOpen, onClose, initialDescription, detectedMembers }) {
    const [description, setDescription] = useState(initialDescription || '');
    const [copied, setCopied] = useState(false);

    React.useEffect(() => {
        setDescription(initialDescription || '');
        setCopied(false);
    }, [initialDescription]);

    const handleCopy = async () => {
        try {
            // Modern clipboard API
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(description);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            } else {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = description;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();

                try {
                    document.execCommand('copy');
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                } catch (err) {
                    console.error('Fallback copy failed:', err);
                    alert('コピーに失敗しました。手動でテキストを選択してコピーしてください。');
                } finally {
                    document.body.removeChild(textArea);
                }
            }
        } catch (err) {
            console.error('Failed to copy text:', err);
            alert('コピーに失敗しました。手動でテキストを選択してコピーしてください。');
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
                onClick={onClose}
            ></div>

            {/* Modal */}
            <div className="flex items-center justify-center min-h-screen p-4">
                <div className="relative bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
                    {/* Header */}
                    <div className="flex items-center justify-between p-6 border-b">
                        <h2 className="text-2xl font-bold text-gray-900">
                            動画概要欄
                        </h2>
                        <button
                            onClick={onClose}
                            className="text-gray-400 hover:text-gray-600 text-2xl"
                        >
                            ✕
                        </button>
                    </div>

                    {/* Detected Members */}
                    {detectedMembers && detectedMembers.length > 0 && (
                        <div className="px-6 py-4 bg-blue-50 border-b">
                            <h3 className="text-sm font-semibold text-blue-900 mb-2">
                                検出されたメンバー:
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {detectedMembers.map((member, index) => (
                                    <span
                                        key={index}
                                        className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                                    >
                                        {member.name_ja} ({member.generation})
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Description Editor */}
                    <div className="flex-1 p-6 overflow-y-auto">
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="w-full h-full min-h-[400px] p-4 border border-gray-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                            placeholder="概要欄の内容がここに表示されます..."
                        />
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between p-6 border-t bg-gray-50">
                        <div className="text-sm text-gray-600">
                            {description.length} 文字
                        </div>
                        <div className="flex space-x-3">
                            <button
                                onClick={onClose}
                                className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors"
                            >
                                閉じる
                            </button>
                            <button
                                onClick={handleCopy}
                                className={`px-6 py-2 rounded-lg transition-colors ${
                                    copied
                                        ? 'bg-green-600 text-white'
                                        : 'bg-blue-600 text-white hover:bg-blue-700'
                                }`}
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
