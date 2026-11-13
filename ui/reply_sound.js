// The audio context is unlocked by a real interaction, never by autoplay.
function configureTiaReplySound(settings) {
  try {
    const host = window.parent;
    if (!host.__tiaReplySound) {
      const state = {enabled: true, context: null, lastEvent: null};
      state.unlock = () => {
        if (!state.enabled) return;
        const Audio = host.AudioContext || host.webkitAudioContext;
        if (!Audio) return;
        if (!state.context) state.context = new Audio();
        if (state.context.state === 'suspended') state.context.resume().catch(() => {});
      };
      state.markPending = () => {
        const input = host.document.querySelector('[data-testid="stChatInput"] textarea');
        const text = input && input.value.trim();
        if (!text || input.disabled) return;
        const pending = host.document.querySelector('[data-tia-pending-text]');
        if (pending) pending.textContent = text;
        host.document.documentElement.dataset.tiaReplyPending = 'true';
        const transcript = host.document.querySelector('.st-key-chat_transcript');
        if (transcript) transcript.scrollTop = transcript.scrollHeight;
      };
      host.document.addEventListener('keydown', event => {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing &&
            event.target.closest('[data-testid="stChatInput"]')) state.markPending();
      }, {capture: true});
      host.document.addEventListener('pointerdown', event => {
        if (event.target.closest('[data-testid="stChatInputSubmitButton"]')) state.markPending();
      }, {capture: true});
      host.document.addEventListener('pointerdown', state.unlock, {capture: true});
      host.document.addEventListener('keydown', state.unlock, {capture: true});
      state.notify = event => {
        if (!event || event === state.lastEvent) return;
        state.lastEvent = event;
        if (!state.enabled || !state.context || state.context.state !== 'running') {
          host.document.documentElement.dataset.tiaReplySound = state.enabled ? 'blocked' : 'muted';
          return;
        }
        host.document.documentElement.dataset.tiaReplySound = 'played';
        const ctx = state.context, start = ctx.currentTime;
        [660, 880].forEach((frequency, index) => {
          const tone = ctx.createOscillator(), gain = ctx.createGain();
          const time = start + index * 0.075;
          tone.type = 'sine'; tone.frequency.value = frequency;
          gain.gain.setValueAtTime(0, time);
          gain.gain.linearRampToValueAtTime(0.035, time + 0.012);
          gain.gain.exponentialRampToValueAtTime(0.0001, time + 0.16);
          tone.connect(gain); gain.connect(ctx.destination);
          tone.start(time); tone.stop(time + 0.17);
        });
      };
      host.__tiaReplySound = state;
    }
    if (!settings.processing) host.document.documentElement.dataset.tiaReplyPending = 'false';
    host.__tiaReplySound.enabled = settings.enabled;
    host.__tiaReplySound.notify(settings.event);
  } catch (_) { /* Audio is optional; a blocked browser must never interrupt chat. */ }
}
