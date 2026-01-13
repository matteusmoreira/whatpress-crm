import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

const MediaMessageNode = ({ data, selected }) => {
    const mediaType = data.config?.mediaType || 'image';
    const caption = data.config?.caption || '';

    const getMediaIcon = () => {
        switch (mediaType) {
            case 'image': return '🖼️';
            case 'video': return '🎥';
            case 'document': return '📄';
            case 'audio': return '🎵';
            default: return '📎';
        }
    };

    return (
        <div className={`custom-node media-message-node ${selected ? 'selected' : ''}`}>
            <div className="node-header">
                <span className="node-icon">{getMediaIcon()}</span>
                <span className="node-title">{data.label || 'Enviar Mídia'}</span>
            </div>
            <div className="node-body">
                <div className="node-description">
                    {caption || `Enviar ${mediaType}`}
                </div>
            </div>
            <Handle
                type="target"
                position={Position.Top}
                className="custom-handle"
            />
            <Handle
                type="source"
                position={Position.Bottom}
                className="custom-handle"
            />
        </div>
    );
};

export default memo(MediaMessageNode);
