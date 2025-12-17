import React, { useState } from 'react';

export default function TwitterModal({ isOpen, onClose, initialText }) {
    const [text, setText] = useState(initialText || '');
    const [copied, setCopied] = useState(false);

    React.useEffect(() => {
        setText(initialText || '');
        setCopied(false);
    }, [initialText]);

    const handleCopy = async () => {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            } else {
                const textArea = document.createElement('textarea');
                textArea.value = text;
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
                <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col">
                    {/* Header */}
                    <div className="flex items-center justify-between p-6 border-b">
                        <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                            <span className="text-blue-400">🐦</span> Twitter PR文章
                        </h2>
                        <button
                            onClick={onClose}
                            className="text-gray-400 hover:text-gray-600 text-2xl"
                        >
                            ✕
                        </button>
                    </div>

                    {/* Editor */}
                    <div className="flex-1 p-6 overflow-y-auto">
                        <textarea
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            className="w-full h-full min-h-[200px] p-4 border border-gray-300 rounded-lg font-sans text-base focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                            placeholder="PR文章がここに表示されます..."
                        />
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between p-6 border-t bg-gray-50">
                        <div className={`text-sm ${text.length > 280 ? 'text-red-600 font-bold' : 'text-gray-600'}`}>
                            {text.length} 文字
                            {text.length > 280 && <span className="ml-2 text-xs">(280文字を超えています)</span>}
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
                                className={`px-6 py-2 rounded-lg transition-colors ${copied
                                        ? 'bg-green-600 text-white'
                                        : 'bg-blue-400 text-white hover:bg-blue-500' // Twitter blue
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
