'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { getSocketIoUrl } from '@/lib/api';
import { useAuthStore } from './useAuthStore';

interface SocketMessage {
  type: string;
  data: any;
  timestamp: string;
}

interface UseSocketOptions {
  autoConnect?: boolean;
  channels?: string[];
  onMessage?: (message: SocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
}

export function useSocket(options: UseSocketOptions = {}) {
  const {
    autoConnect = true,
    channels = [],
    onMessage,
    onConnect,
    onDisconnect,
    onError,
  } = options;

  const socketRef = useRef<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<SocketMessage | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const { accessToken } = useAuthStore();

  const connect = useCallback(() => {
    if (socketRef.current?.connected) return;

    const socket = io(getSocketIoUrl(), {
      auth: { token: accessToken },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socket.on('connect', () => {
      setIsConnected(true);
      setError(null);
      onConnect?.();

      // Subscribe to channels
      channels.forEach((channel) => {
        socket.emit('subscribe', { channel });
      });
    });

    socket.on('disconnect', (reason) => {
      setIsConnected(false);
      onDisconnect?.();
    });

    socket.on('connect_error', (err) => {
      setError(new Error(err.message));
      onError?.(new Error(err.message));
    });

    socket.on('message', (message: SocketMessage) => {
      setLastMessage(message);
      onMessage?.(message);
    });

    // Handle specific event types
    socket.on('alert', (data) => {
      setLastMessage({ type: 'alert', data, timestamp: new Date().toISOString() });
      onMessage?.({ type: 'alert', data, timestamp: new Date().toISOString() });
    });

    socket.on('congestion_update', (data) => {
      setLastMessage({ type: 'congestion_update', data, timestamp: new Date().toISOString() });
      onMessage?.({ type: 'congestion_update', data, timestamp: new Date().toISOString() });
    });

    socket.on('train_update', (data) => {
      setLastMessage({ type: 'train_update', data, timestamp: new Date().toISOString() });
      onMessage?.({ type: 'train_update', data, timestamp: new Date().toISOString() });
    });

    socket.on('station_update', (data) => {
      setLastMessage({ type: 'station_update', data, timestamp: new Date().toISOString() });
      onMessage?.({ type: 'station_update', data, timestamp: new Date().toISOString() });
    });

    socket.on('system_status', (data) => {
      setLastMessage({ type: 'system_status', data, timestamp: new Date().toISOString() });
      onMessage?.({ type: 'system_status', data, timestamp: new Date().toISOString() });
    });

    socket.on('prediction', (data) => {
      setLastMessage({ type: 'prediction', data, timestamp: new Date().toISOString() });
      onMessage?.({ type: 'prediction', data, timestamp: new Date().toISOString() });
    });

    socketRef.current = socket;
  }, [accessToken, channels, onConnect, onDisconnect, onError, onMessage]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    }
  }, []);

  const subscribe = useCallback((channel: string) => {
    socketRef.current?.emit('subscribe', { channel });
  }, []);

  const unsubscribe = useCallback((channel: string) => {
    socketRef.current?.emit('unsubscribe', { channel });
  }, []);

  const send = useCallback((event: string, data: any) => {
    socketRef.current?.emit(event, data);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect && accessToken) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, accessToken, connect, disconnect]);

  // Reconnect when token changes
  useEffect(() => {
    if (accessToken && socketRef.current) {
      disconnect();
      connect();
    }
  }, [accessToken, connect, disconnect]);

  return {
    socket: socketRef.current,
    isConnected,
    lastMessage,
    error,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    send,
  };
}

// Specialized hooks for different channels
export function useAlertsSocket(onAlert?: (alert: any) => void) {
  return useSocket({
    channels: ['alerts'],
    onMessage: (message) => {
      if (message.type === 'alert' && onAlert) {
        onAlert(message.data);
      }
    },
  });
}

export function useCongestionSocket(onUpdate?: (data: any) => void) {
  return useSocket({
    channels: ['congestion'],
    onMessage: (message) => {
      if (message.type === 'congestion_update' && onUpdate) {
        onUpdate(message.data);
      }
    },
  });
}

export function useTrainSocket(onUpdate?: (data: any) => void) {
  return useSocket({
    channels: ['train_updates'],
    onMessage: (message) => {
      if (message.type === 'train_update' && onUpdate) {
        onUpdate(message.data);
      }
    },
  });
}

export function useStationSocket(onUpdate?: (data: any) => void) {
  return useSocket({
    channels: ['station_updates'],
    onMessage: (message) => {
      if (message.type === 'station_update' && onUpdate) {
        onUpdate(message.data);
      }
    },
  });
}

export function useSystemStatusSocket(onUpdate?: (data: any) => void) {
  return useSocket({
    channels: ['system_status'],
    onMessage: (message) => {
      if (message.type === 'system_status' && onUpdate) {
        onUpdate(message.data);
      }
    },
  });
}

export function usePredictionSocket(onUpdate?: (data: any) => void) {
  return useSocket({
    channels: ['predictions'],
    onMessage: (message) => {
      if (message.type === 'prediction' && onUpdate) {
        onUpdate(message.data);
      }
    },
  });
}