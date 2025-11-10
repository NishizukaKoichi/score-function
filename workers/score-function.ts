import { scoreFunction, DEFAULT_CONFIG, ScoreFunctionConfig, MetricsInput } from "../tools/score_function";

export default {
  async fetch(req: Request): Promise<Response> {
    if (req.method !== "POST") {
      return new Response("POST only", { status: 405 });
    }
    try {
      const payload = await req.json();
      const config: ScoreFunctionConfig = { ...DEFAULT_CONFIG, ...(payload.config ?? {}) };
      const metrics: MetricsInput | undefined = payload.metrics;
      if (!metrics) {
        return new Response(JSON.stringify({ error: "metrics payload is required" }), {
          status: 400,
          headers: { "content-type": "application/json" },
        });
      }
      const result = scoreFunction(config, metrics);
      return new Response(JSON.stringify(result), {
        headers: { "content-type": "application/json" },
      });
    } catch (error) {
      return new Response(
        JSON.stringify({ error: (error as Error).message || "unexpected error" }),
        {
          status: 500,
          headers: { "content-type": "application/json" },
        },
      );
    }
  },
};
