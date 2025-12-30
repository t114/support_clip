import React, { useState, useEffect } from 'react';

export default function EmojiSyncModal({ isOpen, onClose, channelId, onSyncComplete }) {
    const [jsonInput, setJsonInput] = useState('');
    const [manualChannelId, setManualChannelId] = useState('');
    const [status, setStatus] = useState('idle'); // idle, syncing, success, error
    const [message, setMessage] = useState('');

    // Pre-fill manualChannelId when props change or JSON is pasted
    useEffect(() => {
        if (channelId && !manualChannelId) {
            setManualChannelId(channelId);
        }
    }, [channelId]);

    // Handle JSON input changes to auto-detect channelId
    const handleJsonChange = (e) => {
        const val = e.target.value;
        setJsonInput(val);
        try {
            const data = JSON.parse(val);
            if (data.channelId && data.channelId !== 'UNKNOWN_CHANNEL') {
                setManualChannelId(data.channelId);
            }
        } catch (e) {
            // Not partial JSON yet
        }
    };

    if (!isOpen) return null;

    const handleSync = async () => {
        try {
            const data = JSON.parse(jsonInput);
            const targetChannelId = manualChannelId || data.channelId || channelId;

            if (!targetChannelId || targetChannelId === 'UNKNOWN_CHANNEL') {
                throw new Error('チャンネルIDが必要です。下のボックスに入力するか、スクリプトを再実行してください。');
            }

            if (!data.emojis || Object.keys(data.emojis).length === 0) {
                throw new Error('スタンプデータが見つかりません。');
            }

            setStatus('syncing');
            setMessage('スタンプをバックエンドと同期中...');

            const response = await fetch('/youtube/sync-emojis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel_id: targetChannelId,
                    emojis: data.emojis
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '同期に失敗しました');
            }

            const result = await response.json();
            setStatus('success');
            setMessage(`✓ ${result.saved_count}個のスタンプを同期・保存しました！`);

            if (onSyncComplete) {
                onSyncComplete(targetChannelId);
            }

            setTimeout(() => {
                onClose();
                setStatus('idle');
                setJsonInput('');
                setManualChannelId('');
                setMessage('');
            }, 2000);

        } catch (e) {
            console.error(e);
            setStatus('error');
            setMessage('エラー: ' + e.message);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[10001] flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in duration-200">
                <div className="bg-gradient-to-r from-red-600 to-red-500 p-6 text-white text-center">
                    <h2 className="text-2xl font-bold">メンバー限定スタンプ同期</h2>
                    <p className="text-red-50 opacity-90 text-sm mt-1">YouTubeから取得したデータを貼り付けてください</p>
                </div>

                <div className="p-6 space-y-4">
                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">チャンネルID (UC...)</label>
                        <input
                            type="text"
                            value={manualChannelId}
                            onChange={(e) => setManualChannelId(e.target.value)}
                            placeholder="UC..."
                            className="w-full p-2.5 border rounded-lg text-sm font-mono focus:ring-2 focus:ring-red-500 outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">JSONデータ</label>
                        <textarea
                            value={jsonInput}
                            onChange={handleJsonChange}
                            placeholder='{ "channelId": "...", "emojis": { ... } }'
                            className="w-full h-40 p-3 border rounded-xl font-mono text-xs focus:ring-2 focus:ring-red-500 focus:border-red-500 outline-none transition-all shadow-inner bg-gray-50/50"
                        />
                    </div>

                    {message && (
                        <div className={`p-3 rounded-xl text-sm font-medium ${status === 'success' ? 'bg-green-100 text-green-700 animate-pulse' :
                                status === 'error' ? 'bg-red-100 text-red-700' :
                                    'bg-blue-100 text-blue-700'
                            }`}>
                            {message}
                        </div>
                    )}

                    <div className="flex gap-3 pt-2">
                        <button
                            onClick={onClose}
                            className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 font-bold transition-colors"
                        >
                            キャンセル
                        </button>
                        <button
                            onClick={handleSync}
                            disabled={!jsonInput || status === 'syncing' || !manualChannelId}
                            className="flex-1 px-4 py-3 bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:bg-gray-300 font-bold shadow-lg shadow-red-200/50 transition-all active:scale-[0.98]"
                        >
                            {status === 'syncing' ? '同期中...' : '同期開始'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
