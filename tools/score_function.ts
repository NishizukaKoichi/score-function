export type Face = "spec" | "code" | "test" | "sec" | "pr" | "dep";

export interface GateConfig {
  min_each: number;
  min_geo: number;
  floor_each: number;
}

export interface ThresholdConfig {
  spec: { ambig_tau: number; conflict_tau: number };
  code: { cc_tau: number };
  test: { low_mt_tau: number; low_cv_tau: number };
  pr: { risk_tau: number };
  dep: { perf_reg_tau: number; cfr_tau: number };
}

export interface WeightConfig {
  spec: { RC: number; TR: number; AM_inv: number; CN_inv: number; EX: number };
  code: { SA: number; CC_inv: number; DP_inv: number; DE: number; DT: number; PF: number };
  test: { CV: number; MT: number; FL_inv: number; SK_inv: number; ST: number };
  sec: { VV: number; SE: number; DPV_inv: number; AT: number; ML: number };
  pr: { RR: number; RK_inv: number; DV: number; RB_inv: number; CI: number };
  dep: { SR: number; CFR_inv: number; MT_inv: number; RBK_inv: number; PRG_inv: number; EB_inv: number };
}

export interface ScoreFunctionConfig {
  version?: number;
  profile?: string;
  k_steep?: number;
  gate: GateConfig;
  external_weights: Record<string, Partial<Record<Face, number>>>;
  thresholds: ThresholdConfig;
  weights: WeightConfig;
}

export interface MetricsInput {
  spec: { RC: number; TR: number; AM: number; CN: number; EX: number };
  code: { SA: number; CC: number; DP: number; DE: number; DT: number; PF: number };
  test: { CV: number; MT: number; FL: number; SK: number; ST: number };
  sec: { CVSS_sum: number; SE: number; dep_vulns: number; AT: number; ML: number; critical_count?: number };
  pr: { RR: number; risk: number; DV: number; RB: number; CI: number };
  dep: { SR: number; CFR: number; MT: number; RBK: number; PRG: number; EB: number };
  uncertainty_sigma?: number;
}

export interface ScoreFunctionResult {
  faces: Record<Face, number>;
  weighted_faces: Record<Face, number>;
  geo: number;
  final: number;
  gate_ok: boolean;
  profile: string;
}

const FACE_ORDER: Face[] = ["spec", "code", "test", "sec", "pr", "dep"];

const clip = (value: number, lower = 0, upper = 1): number =>
  Math.max(lower, Math.min(upper, value));

const logistic = (x: number, tau: number, k: number): number =>
  1 / (1 + Math.exp(-k * (x - tau)));

const penalty = (scale: number, value: number, tau: number, k: number): number =>
  1 - scale * logistic(value, tau, k);

const computeFaces = (config: ScoreFunctionConfig, metrics: MetricsInput): Record<Face, number> => {
  const { weights, thresholds } = config;
  const k = config.k_steep ?? 14;
  const faces: Record<Face, number> = {
    spec: 0,
    code: 0,
    test: 0,
    sec: 0,
    pr: 0,
    dep: 0,
  };

  const spec = metrics.spec;
  const specScore =
    100 *
    (weights.spec.RC * clip(spec.RC) +
      weights.spec.TR * clip(spec.TR) +
      weights.spec.AM_inv * (1 - clip(spec.AM)) +
      weights.spec.CN_inv * (1 - clip(spec.CN)) +
      weights.spec.EX * clip(spec.EX));
  const specPenalty =
    penalty(0.3, clip(spec.AM), thresholds.spec.ambig_tau, k) *
    penalty(0.3, clip(spec.CN), thresholds.spec.conflict_tau, k);
  faces.spec = specScore * specPenalty;

  const code = metrics.code;
  const codeScore =
    100 *
    (weights.code.SA * clip(code.SA) +
      weights.code.CC_inv * (1 - clip(code.CC)) +
      weights.code.DP_inv * (1 - clip(code.DP)) +
      weights.code.DE * clip(code.DE) +
      weights.code.DT * clip(code.DT) +
      weights.code.PF * clip(code.PF));
  const codePenalty = penalty(0.4, clip(code.CC), thresholds.code.cc_tau, k);
  faces.code = codeScore * codePenalty;

  const test = metrics.test;
  const testScore =
    100 *
    (weights.test.CV * clip(test.CV) +
      weights.test.MT * clip(test.MT) +
      weights.test.FL_inv * (1 - clip(test.FL)) +
      weights.test.SK_inv * (1 - clip(test.SK)) +
      weights.test.ST * clip(test.ST));
  const testPenalty =
    penalty(0.5, 1 - clip(test.MT), thresholds.test.low_mt_tau, k) *
    penalty(0.3, 1 - clip(test.CV), thresholds.test.low_cv_tau, k);
  faces.test = testScore * testPenalty;

  const sec = metrics.sec;
  const vv = 1 - clip(sec.CVSS_sum);
  const secScore =
    100 *
    (weights.sec.VV * vv +
      weights.sec.SE * clip(sec.SE) +
      weights.sec.DPV_inv * (1 - clip(sec.dep_vulns)) +
      weights.sec.AT * clip(sec.AT) +
      weights.sec.ML * clip(sec.ML));
  faces.sec = (sec.critical_count ?? 0) >= 1 ? secScore * 0.25 : secScore;

  const pr = metrics.pr;
  const prScore =
    100 *
    (weights.pr.RR * clip(pr.RR) +
      weights.pr.RK_inv * (1 - clip(pr.risk)) +
      weights.pr.DV * clip(pr.DV) +
      weights.pr.RB_inv * (1 - clip(pr.RB)) +
      weights.pr.CI * clip(pr.CI));
  const prPenalty = penalty(0.4, clip(pr.risk), thresholds.pr.risk_tau, k);
  faces.pr = prScore * prPenalty;

  const dep = metrics.dep;
  const depScore =
    100 *
    (weights.dep.SR * clip(dep.SR) +
      weights.dep.CFR_inv * (1 - clip(dep.CFR)) +
      weights.dep.MT_inv * (1 - clip(dep.MT)) +
      weights.dep.RBK_inv * (1 - clip(dep.RBK)) +
      weights.dep.PRG_inv * (1 - clip(dep.PRG)) +
      weights.dep.EB_inv * (1 - clip(dep.EB)));
  const depPenalty =
    penalty(0.5, clip(dep.PRG), thresholds.dep.perf_reg_tau, k) *
    penalty(0.3, clip(dep.CFR), thresholds.dep.cfr_tau, k);
  faces.dep = depScore * depPenalty;

  return faces;
};

export const DEFAULT_CONFIG: ScoreFunctionConfig = {
  version: 1,
  profile: "sre",
  k_steep: 14,
  gate: {
    min_each: 70,
    min_geo: 80,
    floor_each: 5,
  },
  external_weights: {
    sre: { spec: 1.0, code: 1.0, test: 1.0, sec: 1.2, pr: 1.0, dep: 1.2 },
    speed: { spec: 1.15, code: 1.15, test: 1.15, sec: 0.9, pr: 1.15, dep: 0.9 },
  },
  thresholds: {
    spec: { ambig_tau: 0.6, conflict_tau: 0.6 },
    code: { cc_tau: 0.7 },
    test: { low_mt_tau: 0.6, low_cv_tau: 0.7 },
    pr: { risk_tau: 0.7 },
    dep: { perf_reg_tau: 0.6, cfr_tau: 0.5 },
  },
  weights: {
    spec: { RC: 0.3, TR: 0.25, AM_inv: 0.2, CN_inv: 0.15, EX: 0.1 },
    code: { SA: 0.28, CC_inv: 0.2, DP_inv: 0.12, DE: 0.18, DT: 0.12, PF: 0.1 },
    test: { CV: 0.32, MT: 0.32, FL_inv: 0.16, SK_inv: 0.1, ST: 0.1 },
    sec: { VV: 0.34, SE: 0.2, DPV_inv: 0.16, AT: 0.2, ML: 0.1 },
    pr: { RR: 0.28, RK_inv: 0.22, DV: 0.18, RB_inv: 0.12, CI: 0.2 },
    dep: { SR: 0.22, CFR_inv: 0.22, MT_inv: 0.18, RBK_inv: 0.12, PRG_inv: 0.16, EB_inv: 0.1 },
  },
};

export const scoreFunction = (config: ScoreFunctionConfig, metrics: MetricsInput): ScoreFunctionResult => {
  const faces = computeFaces(config, metrics);
  const profileWeights = config.external_weights[config.profile ?? "sre"] ?? {};
  const weightedFaces = FACE_ORDER.reduce<Record<Face, number>>((acc, face) => {
    acc[face] = faces[face] * (profileWeights[face] ?? 1);
    return acc;
  }, {} as Record<Face, number>);

  const adjusted = FACE_ORDER.map((face) =>
    Math.max(config.gate.floor_each, weightedFaces[face]) / 100,
  );
  const geo = 100 * Math.pow(adjusted.reduce((prod, val) => prod * val, 1), 1 / adjusted.length);
  const sigma = clip(metrics.uncertainty_sigma ?? 0);
  const final = geo * (1 - 0.1 * sigma);
  const gateOk =
    Math.min(...FACE_ORDER.map((face) => faces[face])) >= config.gate.min_each &&
    geo >= config.gate.min_geo;

  const round2 = (value: number) => Math.round(value * 1e4) / 1e4;

  return {
    faces: FACE_ORDER.reduce<Record<Face, number>>((acc, face) => {
      acc[face] = round2(faces[face]);
      return acc;
    }, {} as Record<Face, number>),
    weighted_faces: FACE_ORDER.reduce<Record<Face, number>>((acc, face) => {
      acc[face] = round2(weightedFaces[face]);
      return acc;
    }, {} as Record<Face, number>),
    geo: round2(geo),
    final: round2(final),
    gate_ok: gateOk,
    profile: config.profile ?? "sre",
  };
};
