import { useEffect, useRef } from 'react';
import { streamChatMessage } from './claw-manager-client';
import { useAidaSession } from './aida-session';
import {
  CLAW_REPLY_DELTA_EVENT,
  CLAW_REPLY_DONE_EVENT,
  CLAW_REPLY_ERROR_EVENT,
  CLAW_REPLY_START_EVENT,
  CLAW_SEND_EVENT,
  type ClawSendDetail,
} from './claw-send';

export function AidaChatBridge() {
  const { session, getChatAccess } = useAidaSession();
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    const onSend = async (e: Event) => {
      const detail = (e as CustomEvent<ClawSendDetail>).detail;
      const text = detail?.text?.trim();
      if (!text) return;

      const replyId = `reply-${Date.now()}`;
      emit(CLAW_REPLY_START_EVENT, { id: replyId, body: '' });

      try {
        if (!session) throw new Error('请先登录 AIDA');
        const access = await getChatAccess();
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        await streamChatMessage(
          access,
          {
            session_id: session.sessionId,
            message: text,
            pathname: detail.pathname,
            source: detail.source,
            client_message_id: replyId,
          },
          {
            signal: controller.signal,
            onDelta: (delta) => emit(CLAW_REPLY_DELTA_EVENT, { id: replyId, delta }),
            onDone: () => emit(CLAW_REPLY_DONE_EVENT, { id: replyId }),
            onError: (error) => emit(CLAW_REPLY_ERROR_EVENT, { id: replyId, error }),
          },
        );
      } catch (err) {
        const error = err instanceof Error ? err.message : 'AIDA 发送失败';
        emit(CLAW_REPLY_ERROR_EVENT, { id: replyId, error });
      }
    };

    window.addEventListener(CLAW_SEND_EVENT, onSend);
    return () => window.removeEventListener(CLAW_SEND_EVENT, onSend);
  }, [getChatAccess, session]);

  return null;
}

function emit(type: string, detail: Record<string, unknown>) {
  window.dispatchEvent(new CustomEvent(type, { detail }));
}
