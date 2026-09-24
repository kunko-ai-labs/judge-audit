/**
 * Bridge: AI SDK `experimental_evaluate` -> JSON over stdio.
 *
 * Jev is an *evaluation* model, not a chat model: it cannot be called via
 * /v1/chat/completions. The only supported path through AI Gateway is the
 * AI SDK evaluate API, so this tiny Node process speaks that API and hands
 * plain JSON back to the Python harness.
 *
 * stdin:  {"items": [{"state": str, "questions": {name: {type, instructions, criteria?}}}]}
 * stdout: JSON array, one result per item:
 *         {ok, answers, providerMetadata, usage, latencyMs} or {ok:false, error, latencyMs}
 *
 * Auth: AI_GATEWAY_API_KEY env var (AI SDK convention). Model override: JEV_MODEL.
 */
import { experimental_evaluate as evaluate } from 'ai';

async function readStdin() {
  let data = '';
  for await (const chunk of process.stdin) data += chunk;
  return JSON.parse(data);
}

const input = await readStdin();
const model = process.env.JEV_MODEL || 'typesafe-ai/jev';
// Zero Data Retention needs a Pro/Enterprise gateway plan; Hobby can't use it.
const providerOptions = process.env.JEV_ZDR === '1'
  ? { gateway: { zeroDataRetention: true } }
  : undefined;
const out = [];

for (const item of input.items) {
  const t0 = Date.now();
  try {
    const r = await evaluate({
      model,
      state: item.state,
      questions: item.questions,
      maxRetries: 1, // gateway free tier is rate-limited; outer backoff handles it
      ...(providerOptions ? { providerOptions } : {}),
    });
    out.push({
      ok: true,
      answers: r.answers ?? null,
      providerMetadata: r.providerMetadata ?? null,
      usage: r.usage ?? null,
      // what the gateway says it served, when it says it (null otherwise)
      response: r.response ? { modelId: r.response.modelId ?? null, id: r.response.id ?? null } : null,
      latencyMs: Date.now() - t0,
    });
  } catch (e) {
    out.push({ ok: false, error: String((e && e.message) || e), latencyMs: Date.now() - t0 });
  }
}

process.stdout.write(JSON.stringify(out));
