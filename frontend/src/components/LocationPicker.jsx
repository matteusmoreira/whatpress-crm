import React, { useState, useEffect } from 'react';
import { MapPin, Navigation, Send, X, Loader } from 'lucide-react';
import { GlassButton } from './GlassCard';
import { cn } from '../lib/utils';

// Location Picker Component
const LocationPicker = ({ onSend, onCancel }) => {
    const [location, setLocation] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const getCurrentLocation = () => {
        if (!navigator.geolocation) {
            setError('Geolocalização não suportada pelo seu navegador');
            return;
        }

        setLoading(true);
        setError(null);

        navigator.geolocation.getCurrentPosition(
            (position) => {
                setLocation({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy
                });
                setLoading(false);
            },
            (err) => {
                setLoading(false);
                switch (err.code) {
                    case err.PERMISSION_DENIED:
                        setError('Permissão de localização negada');
                        break;
                    case err.POSITION_UNAVAILABLE:
                        setError('Localização indisponível');
                        break;
                    case err.TIMEOUT:
                        setError('Tempo esgotado ao buscar localização');
                        break;
                    default:
                        setError('Erro ao obter localização');
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    };

    const handleSend = () => {
        if (location) {
            onSend(location);
        }
    };

    return (
        <div className="p-4 bg-emerald-900/90 backdrop-blur-xl border border-white/20 rounded-xl">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-emerald-400" />
                    <span className="text-white font-medium">Enviar Localização</span>
                </div>
                <button
                    onClick={onCancel}
                    className="p-2 text-white/40 hover:text-white hover:bg-white/10 rounded-lg"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>

            {!location ? (
                <div className="text-center py-4">
                    {loading ? (
                        <div className="flex flex-col items-center gap-3">
                            <Loader className="w-8 h-8 text-emerald-400 animate-spin" />
                            <p className="text-white/60 text-sm">Obtendo localização...</p>
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center gap-3">
                            <MapPin className="w-8 h-8 text-red-400" />
                            <p className="text-red-400 text-sm">{error}</p>
                            <button
                                onClick={getCurrentLocation}
                                className="text-emerald-400 text-sm hover:underline"
                            >
                                Tentar novamente
                            </button>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center gap-3">
                            <Navigation className="w-12 h-12 text-emerald-400" />
                            <p className="text-white/60 text-sm">
                                Clique para compartilhar sua localização atual
                            </p>
                            <GlassButton onClick={getCurrentLocation}>
                                <Navigation className="w-4 h-4 mr-2" />
                                Obter Localização
                            </GlassButton>
                        </div>
                    )}
                </div>
            ) : (
                <div className="space-y-4">
                    {/* Map Preview */}
                    <div className="relative h-40 rounded-lg overflow-hidden bg-black/20">
                        <img
                            src={`https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/pin-s+22c55e(${location.longitude},${location.latitude})/${location.longitude},${location.latitude},14,0/400x200@2x?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw`}
                            alt="Mapa"
                            className="w-full h-full object-cover"
                            onError={(e) => {
                                // Fallback if mapbox fails
                                e.target.style.display = 'none';
                            }}
                        />
                        <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                            <div className="text-center text-white p-4">
                                <MapPin className="w-8 h-8 mx-auto mb-2 text-emerald-400" />
                                <p className="text-sm font-mono">
                                    {location.latitude.toFixed(6)}, {location.longitude.toFixed(6)}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 text-white/50 text-xs">
                        <Navigation className="w-3 h-3" />
                        <span>Precisão: ~{Math.round(location.accuracy)}m</span>
                    </div>

                    <div className="flex gap-2">
                        <button
                            onClick={() => setLocation(null)}
                            className="flex-1 px-4 py-2 text-white/60 hover:text-white transition-colors"
                        >
                            Cancelar
                        </button>
                        <GlassButton onClick={handleSend} className="flex-1">
                            <Send className="w-4 h-4 mr-2" />
                            Enviar Localização
                        </GlassButton>
                    </div>
                </div>
            )}
        </div>
    );
};

// Location Display Component (for received locations)
export const LocationDisplay = ({ latitude, longitude, name }) => {
    const mapUrl = `https://www.google.com/maps?q=${latitude},${longitude}`;
    const staticMapUrl = `https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/pin-s+22c55e(${longitude},${latitude})/${longitude},${latitude},14,0/300x150@2x?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw`;

    return (
        <a
            href={mapUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-lg overflow-hidden hover:opacity-90 transition-opacity"
        >
            <div className="relative">
                <img
                    src={staticMapUrl}
                    alt="Localização"
                    className="w-full h-32 object-cover"
                    onError={(e) => {
                        e.target.style.display = 'none';
                    }}
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                    <div className="text-center text-white p-2">
                        <MapPin className="w-6 h-6 mx-auto mb-1 text-emerald-400" />
                        {name && <p className="text-sm font-medium">{name}</p>}
                        <p className="text-xs font-mono opacity-80">
                            {latitude.toFixed(4)}, {longitude.toFixed(4)}
                        </p>
                    </div>
                </div>
            </div>
            <div className="bg-black/20 px-3 py-2 flex items-center gap-2 text-sm">
                <MapPin className="w-4 h-4 text-emerald-400" />
                <span className="text-white/70">Abrir no Google Maps</span>
            </div>
        </a>
    );
};

export default LocationPicker;
