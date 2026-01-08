import React, { useState, useEffect } from 'react';

function EmojiManager() {
    const [channels, setChannels] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [showImportModal, setShowImportModal] = useState(false);
    const [importJson, setImportJson] = useState('');
    const [parsedData, setParsedData] = useState(null);
    const [importStatus, setImportStatus] = useState(''); // '', 'importing', 'success', 'error'
    const [selectedChannel, setSelectedChannel] = useState(null);
    const [channelDetail, setChannelDetail] = useState(null);
    const [isDetailLoading, setIsDetailLoading] = useState(false);

    const fetchEmojis = async () => {
        setIsLoading(true);
        try {
            const res = await fetch('/api/emojis');
            if (!res.ok) throw new Error('Failed to fetch emojis');
            const data = await res.json();
            setChannels(data.channels || []);
        } catch (e) {
            setError(e.message);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchChannelDetail = async (cid) => {
        setIsDetailLoading(true);
        try {
            const res = await fetch(`/api/emojis/${cid}`);
            if (!res.ok) throw new Error('Failed to fetch channel details');
            const data = await res.json();
            setChannelDetail(data);
            setSelectedChannel(cid);
        } catch (e) {
            alert(e.message);
        } finally {
            setIsDetailLoading(false);
        }
    };

    useEffect(() => {
        fetchEmojis();
    }, []);

    const handleParse = () => {
        try {
            const data = JSON.parse(importJson);
            if (!data.channelId || !data.emojis) {
                throw new Error('Invalid data format. Expected { channelId, emojis }');
            }
            setParsedData(data);
        } catch (e) {
            alert(e.message);
        }
    };

    const handleImport = async () => {
        if (!parsedData) return;
        try {
            setImportStatus('importing');
            const res = await fetch('/youtube/sync-emojis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel_id: parsedData.channelId,
                    channel_name: parsedData.channelName,
                    emojis: parsedData.emojis
                })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Import failed');
            }

            setImportStatus('success');
            setImportJson('');
            setParsedData(null);
            setTimeout(() => {
                setShowImportModal(false);
                setImportStatus('');
                fetchEmojis(); // Refresh list
            }, 1500);

        } catch (e) {
            setImportStatus('error');
            alert(e.message);
        }
    };

    const formatDate = (isoStr) => {
        if (!isoStr) return '-';
        try {
            const d = new Date(isoStr);
            return `${d.getFullYear()}/${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
        } catch (e) {
            return isoStr;
        }
    };

    const handleDelete = async (cid, name) => {
        if (!confirm(`${name} のスタンプデータを削除しますか？`)) return;
        try {
            const res = await fetch(`/api/emojis/${cid}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Delete failed');
            fetchEmojis();
        } catch (e) {
            alert(e.message);
        }
    };

    const openModal = () => {
        setImportJson('');
        setParsedData(null);
        setImportStatus('');
        setShowImportModal(true);
    };

    return (
        <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-sm p-8">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-gray-900">メンバースタンプ管理</h2>
                <button
                    onClick={openModal}
                    className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors flex items-center gap-2"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
                    </svg>
                    スタンプ追加 (JSON)
                </button>
            </div>

            {error && (
                <div className="bg-red-50 text-red-700 p-4 rounded-md mb-4">
                    Error: {error}
                </div>
            )}

            {isLoading ? (
                <div className="text-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto"></div>
                    <p className="mt-4 text-gray-500">読み込み中...</p>
                </div>
            ) : (
                <div className="overflow-hidden border rounded-lg">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">チャンネル名 / ID</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">登録日</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">スタンプ数</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">サンプル</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {channels.length === 0 ? (
                                <tr>
                                    <td colSpan="4" className="px-6 py-12 text-center text-gray-500">
                                        登録されているスタンプはありません
                                    </td>
                                </tr>
                            ) : (
                                channels.map((ch) => (
                                    <tr
                                        key={ch.id}
                                        className="hover:bg-gray-50 cursor-pointer transition-colors"
                                        onClick={() => fetchChannelDetail(ch.id)}
                                    >
                                        <td className="px-6 py-4">
                                            <div className="text-sm font-medium text-gray-900">{ch.name}</div>
                                            <div className="text-xs text-gray-500 font-mono mt-1">{ch.id}</div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="text-xs text-gray-500">{formatDate(ch.registered_at)}</div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                                {ch.count} 個
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex flex-wrap gap-1 text-xs text-gray-500 font-mono">
                                                {ch.examples.map((ex, i) => (
                                                    <span key={i} className="bg-gray-100 px-1 rounded border border-gray-200">
                                                        {ex}
                                                    </span>
                                                ))}
                                                {ch.count > 5 && <span>...</span>}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                                            <button
                                                onClick={() => handleDelete(ch.id, ch.name)}
                                                className="text-red-600 hover:text-red-900 text-sm font-medium"
                                            >
                                                削除
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Import Modal */}
            {showImportModal && (
                <div className="fixed inset-0 z-[100] overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
                    <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
                        {/* Backdrop */}
                        <div
                            className="fixed inset-0 bg-black/50 transition-opacity"
                            aria-hidden="true"
                            onClick={() => setShowImportModal(false)}
                        ></div>

                        {/* Centering trick */}
                        <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

                        {/* Modal Panel */}
                        <div className="relative inline-block align-middle bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full border border-gray-200">
                            <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                                <div className="sm:flex sm:items-start">
                                    <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
                                        <h3 className="text-lg leading-6 font-bold text-gray-900 mb-4" id="modal-title">
                                            スタンプ情報のインポート
                                        </h3>

                                        {!parsedData ? (
                                            <div className="space-y-4">
                                                <p className="text-sm text-gray-500">
                                                    収集スクリプト(browser_collector.js)の出力JSONを貼り付けてください。
                                                </p>
                                                <textarea
                                                    className="w-full h-80 p-3 border border-gray-300 rounded-lg font-mono text-xs focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                                                    placeholder='{ "channelId": "...", "channelName": "...", "emojis": { ... } }'
                                                    value={importJson}
                                                    onChange={(e) => setImportJson(e.target.value)}
                                                ></textarea>
                                            </div>
                                        ) : (
                                            <div className="space-y-4">
                                                <div className="bg-blue-50 p-4 rounded-md border border-blue-100">
                                                    <h4 className="text-sm font-bold text-blue-900 mb-2">インポート内容の確認</h4>
                                                    <div className="grid grid-cols-3 gap-2 text-sm">
                                                        <div className="text-gray-500">チャンネル名:</div>
                                                        <div className="col-span-2 font-bold">{parsedData.channelName || '不明'}</div>
                                                        <div className="text-gray-500">チャンネルID:</div>
                                                        <div className="col-span-2 font-mono text-xs break-all">{parsedData.channelId}</div>
                                                        <div className="text-gray-500">スタンプ数:</div>
                                                        <div className="col-span-2">{Object.keys(parsedData.emojis).length} 個</div>
                                                    </div>
                                                </div>

                                                <div className="max-h-64 overflow-y-auto border rounded-md p-3 bg-gray-50">
                                                    <div className="flex flex-wrap gap-2">
                                                        {Object.keys(parsedData.emojis).map((key, i) => (
                                                            <div key={i} className="flex items-center gap-1.5 bg-white border border-gray-200 px-2 py-1 rounded text-xs shadow-sm">
                                                                <img src={parsedData.emojis[key]} alt="" className="h-5 w-5 object-contain" />
                                                                <span className="text-gray-700 font-mono">{key}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-2 p-3 bg-yellow-50 rounded border border-yellow-100">
                                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-yellow-600" viewBox="0 0 20 20" fill="currentColor">
                                                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                                    </svg>
                                                    <p className="text-xs text-yellow-800">
                                                        上記のチャンネルに登録します。間違いがないか再度確認してください。
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div className="bg-gray-50 px-4 py-3 sm:px-6 flex flex-row-reverse gap-2">
                                {!parsedData ? (
                                    <button
                                        type="button"
                                        disabled={!importJson.trim()}
                                        onClick={handleParse}
                                        className="inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                                    >
                                        次へ (確認)
                                    </button>
                                ) : (
                                    <button
                                        type="button"
                                        disabled={importStatus === 'importing'}
                                        onClick={handleImport}
                                        className={`inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 text-sm font-medium text-white transition-colors
                                            ${importStatus === 'success' ? 'bg-green-600' : 'bg-green-600 hover:bg-green-700'}
                                            disabled:opacity-50 disabled:cursor-not-allowed`}
                                    >
                                        {importStatus === 'importing' ? 'インポート中...' :
                                            importStatus === 'success' ? '登録完了！' : 'インポートを確定する'}
                                    </button>
                                )}
                                <button
                                    type="button"
                                    onClick={() => {
                                        if (parsedData) {
                                            setParsedData(null);
                                        } else {
                                            setShowImportModal(false);
                                        }
                                    }}
                                    className="inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                                >
                                    {parsedData ? '戻る' : 'キャンセル'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
            {/* Detail Modal */}
            {selectedChannel && channelDetail && (
                <div className="fixed inset-0 z-[110] overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
                    <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
                        <div className="fixed inset-0 bg-black/60 transition-opacity" onClick={() => setSelectedChannel(null)}></div>
                        <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
                        <div className="relative inline-block align-middle bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full border border-gray-200">
                            <div className="bg-white px-6 pt-5 pb-4 sm:p-6 sm:pb-4">
                                <div className="flex justify-between items-start mb-6 border-b pb-4">
                                    <div>
                                        <h3 className="text-xl font-bold text-gray-900">{channelDetail.name}</h3>
                                        <p className="text-sm text-gray-500 font-mono mt-1">{channelDetail.id}</p>
                                    </div>
                                    <button
                                        onClick={() => setSelectedChannel(null)}
                                        className="text-gray-400 hover:text-gray-500"
                                    >
                                        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                                    {channelDetail.emojis.map((emoji, i) => (
                                        <div key={i} className="flex flex-col items-center bg-gray-50 p-4 rounded-lg border border-gray-100 hover:border-blue-200 transition-colors">
                                            <img src={emoji.url} alt={emoji.shortcut} className="h-12 w-12 object-contain mb-3" />
                                            <span className="text-xs text-gray-600 font-mono break-all text-center">{emoji.shortcut}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div className="bg-gray-50 px-6 py-4 flex justify-end">
                                <button
                                    type="button"
                                    onClick={() => setSelectedChannel(null)}
                                    className="px-4 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                                >
                                    閉じる
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );

}

export default EmojiManager;
