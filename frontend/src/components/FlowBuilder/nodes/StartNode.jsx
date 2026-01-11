import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const StartNode = ({ data, selected }) => {
    return (
        <div className={`custom-node start-node ${selected ? 'selected' : ''}`}>
            <div className="node-header">
                <span className="node-icon">🟢</span>
                <span className="node-title">{data.label || 'Início'}</span>
            </div>
            <div className="node-body">
                <div className="node-description">
                    Início do fluxo
                </div>
            </div>
            <Handle
                type="source"
                position={Position.Bottom}
                className="custom-handle"
            />
        </div>
    );
};

export default memo(StartNode);
