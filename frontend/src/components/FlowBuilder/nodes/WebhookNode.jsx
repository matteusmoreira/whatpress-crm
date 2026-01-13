import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

const WebhookNode = ({ data, selected }) => {
    const method = data.config?.method || 'POST';
    const url = data.config?.url || '';

    return (
        <div className={`custom-node webhook-node ${selected ? 'selected' : ''}`}>
            <div className="node-header">
                <span className="node-icon">🌐</span>
                <span className="node-title">{data.label || 'Webhook'}</span>
            </div>
            <div className="node-body">
                <div className="node-description">
                    <span className="webhook-method">{method}</span>
                    {url ? ` ${url.substring(0, 20)}...` : ' Configure o webhook'}
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

export default memo(WebhookNode);
