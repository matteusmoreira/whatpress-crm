import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const TextMessageNode = ({ data, selected }) => {
    const message = data.config?.message || '';
    const preview = message.length > 30 ? `${message.substring(0, 30)}...` : message;

    return (
        <div className={`custom-node text-message-node ${selected ? 'selected' : ''}`}>
            <div className="node-header">
                <span className="node-icon">💬</span>
                <span className="node-title">{data.label || 'Enviar Texto'}</span>
            </div>
            <div className="node-body">
                <div className="node-description">
                    {preview || 'Configure a mensagem'}
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

export default memo(TextMessageNode);
