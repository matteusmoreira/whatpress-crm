import React, { useState, useEffect } from 'react';
import useFlowStore from '../../../store/flowStore';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Textarea } from '../../ui/textarea';
import { Label } from '../../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../ui/select';
import { X, Save } from 'lucide-react';
import { toast } from 'sonner';

const NodeConfigPanel = () => {
    const { selectedNode, updateNode, deleteNode, setSelectedNode, saveFlow } = useFlowStore();
    const [config, setConfig] = useState({});

    useEffect(() => {
        if (selectedNode) {
            setConfig(selectedNode.data?.config || {});
        }
    }, [selectedNode]);

    if (!selectedNode) {
        return (
            <div className="node-config-panel empty">
                <div className="empty-state">
                    <p>Selecione um nó para configurar</p>
                </div>
            </div>
        );
    }

    const handleConfigChange = (key, value) => {
        setConfig(prev => ({ ...prev, [key]: value }));
    };

    const handleSave = () => {
        updateNode(selectedNode.id, { config });
        toast.success('Configuração salva');
    };

    const handleDelete = () => {
        if (window.confirm('Tem certeza que deseja deletar este nó?')) {
            deleteNode(selectedNode.id);
            toast.success('Nó deletado');
        }
    };

    const renderConfigFields = () => {
        switch (selectedNode.type) {
            case 'start':
                return (
                    <>
                        <div className="config-field">
                            <Label>Tipo de Gatilho</Label>
                            <Select
                                value={config.trigger || 'manual'}
                                onValueChange={(value) => handleConfigChange('trigger', value)}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="manual">Manual</SelectItem>
                                    <SelectItem value="keyword">Palavra-chave</SelectItem>
                                    <SelectItem value="schedule">Agendado</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        {config.trigger === 'keyword' && (
                            <div className="config-field">
                                <Label>Palavra-chave</Label>
                                <Input
                                    value={config.keyword || ''}
                                    onChange={(e) => handleConfigChange('keyword', e.target.value)}
                                    placeholder="Digite a palavra-chave"
                                />
                            </div>
                        )}
                    </>
                );

            case 'textMessage':
                return (
                    <div className="config-field">
                        <Label>Mensagem</Label>
                        <Textarea
                            value={config.message || ''}
                            onChange={(e) => handleConfigChange('message', e.target.value)}
                            placeholder="Digite a mensagem..."
                            rows={6}
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                            Use variáveis com {'{nome_variavel}'}
                        </p>
                    </div>
                );

            case 'mediaMessage':
                return (
                    <>
                        <div className="config-field">
                            <Label>Tipo de Mídia</Label>
                            <Select
                                value={config.mediaType || 'image'}
                                onValueChange={(value) => handleConfigChange('mediaType', value)}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="image">Imagem</SelectItem>
                                    <SelectItem value="video">Vídeo</SelectItem>
                                    <SelectItem value="document">Documento</SelectItem>
                                    <SelectItem value="audio">Áudio</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="config-field">
                            <Label>URL da Mídia</Label>
                            <Input
                                value={config.mediaUrl || ''}
                                onChange={(e) => handleConfigChange('mediaUrl', e.target.value)}
                                placeholder="https://exemplo.com/imagem.jpg"
                            />
                        </div>

                        <div className="config-field">
                            <Label>Legenda (opcional)</Label>
                            <Textarea
                                value={config.caption || ''}
                                onChange={(e) => handleConfigChange('caption', e.target.value)}
                                placeholder="Digite uma legenda..."
                                rows={3}
                            />
                        </div>
                    </>
                );

            case 'wait':
                return (
                    <>
                        <div className="config-field">
                            <Label>Duração</Label>
                            <Input
                                type="number"
                                value={config.duration || 1}
                                onChange={(e) => handleConfigChange('duration', parseInt(e.target.value) || 1)}
                                min="1"
                            />
                        </div>

                        <div className="config-field">
                            <Label>Unidade</Label>
                            <Select
                                value={config.unit || 'seconds'}
                                onValueChange={(value) => handleConfigChange('unit', value)}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="seconds">Segundos</SelectItem>
                                    <SelectItem value="minutes">Minutos</SelectItem>
                                    <SelectItem value="hours">Horas</SelectItem>
                                    <SelectItem value="days">Dias</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </>
                );

            case 'conditional':
                return (
                    <>
                        <div className="config-field">
                            <Label>Variável</Label>
                            <Input
                                value={config.condition?.variable || ''}
                                onChange={(e) => handleConfigChange('condition', {
                                    ...config.condition,
                                    variable: e.target.value
                                })}
                                placeholder="nome_da_variavel"
                            />
                        </div>

                        <div className="config-field">
                            <Label>Operador</Label>
                            <Select
                                value={config.condition?.operator || 'equals'}
                                onValueChange={(value) => handleConfigChange('condition', {
                                    ...config.condition,
                                    operator: value
                                })}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="equals">Igual a</SelectItem>
                                    <SelectItem value="contains">Contém</SelectItem>
                                    <SelectItem value="greater">Maior que</SelectItem>
                                    <SelectItem value="less">Menor que</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="config-field">
                            <Label>Valor</Label>
                            <Input
                                value={config.condition?.value || ''}
                                onChange={(e) => handleConfigChange('condition', {
                                    ...config.condition,
                                    value: e.target.value
                                })}
                                placeholder="Valor para comparar"
                            />
                        </div>
                    </>
                );

            case 'variable':
                return (
                    <>
                        <div className="config-field">
                            <Label>Ação</Label>
                            <Select
                                value={config.action || 'set'}
                                onValueChange={(value) => handleConfigChange('action', value)}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="set">Definir</SelectItem>
                                    <SelectItem value="get">Obter</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="config-field">
                            <Label>Nome da Variável</Label>
                            <Input
                                value={config.variableName || ''}
                                onChange={(e) => handleConfigChange('variableName', e.target.value)}
                                placeholder="nome_da_variavel"
                            />
                        </div>

                        {config.action === 'set' && (
                            <div className="config-field">
                                <Label>Valor</Label>
                                <Input
                                    value={config.value || ''}
                                    onChange={(e) => handleConfigChange('value', e.target.value)}
                                    placeholder="Valor da variável"
                                />
                            </div>
                        )}
                    </>
                );

            case 'webhook':
                return (
                    <>
                        <div className="config-field">
                            <Label>Método</Label>
                            <Select
                                value={config.method || 'POST'}
                                onValueChange={(value) => handleConfigChange('method', value)}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="GET">GET</SelectItem>
                                    <SelectItem value="POST">POST</SelectItem>
                                    <SelectItem value="PUT">PUT</SelectItem>
                                    <SelectItem value="DELETE">DELETE</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="config-field">
                            <Label>URL</Label>
                            <Input
                                value={config.url || ''}
                                onChange={(e) => handleConfigChange('url', e.target.value)}
                                placeholder="https://api.exemplo.com/endpoint"
                            />
                        </div>

                        <div className="config-field">
                            <Label>Variável de Resposta (opcional)</Label>
                            <Input
                                value={config.responseVariable || ''}
                                onChange={(e) => handleConfigChange('responseVariable', e.target.value)}
                                placeholder="nome_variavel_resposta"
                            />
                            <p className="text-xs text-muted-foreground mt-1">
                                A resposta da API será armazenada nesta variável
                            </p>
                        </div>
                    </>
                );

            default:
                return <p>Sem configurações disponíveis para este tipo de nó</p>;
        }
    };

    return (
        <div className="node-config-panel">
            <div className="panel-header">
                <h3>Configurar Nó</h3>
                <button
                    onClick={() => setSelectedNode(null)}
                    className="close-btn"
                >
                    <X size={18} />
                </button>
            </div>

            <div className="panel-content">
                <div className="node-info">
                    <div className="node-type-badge">{selectedNode.data?.label}</div>
                    <p className="node-id text-xs text-muted-foreground">ID: {selectedNode.id}</p>
                </div>

                <div className="config-form">
                    {renderConfigFields()}
                </div>
            </div>

            <div className="panel-footer">
                <Button onClick={handleSave} className="w-full mb-2">
                    <Save size={16} className="mr-2" />
                    Salvar Configuração
                </Button>
                <Button
                    variant="destructive"
                    onClick={handleDelete}
                    className="w-full"
                >
                    Deletar Nó
                </Button>
            </div>
        </div>
    );
};

export default NodeConfigPanel;
