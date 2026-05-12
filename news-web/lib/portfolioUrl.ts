const STORAGE_KEY = "portfolioAppOrigin";
const STORAGE_USER_KEY = "portfolioAppUser";
const STORAGE_RESUME_KEY = "portfolioAppResume";

const DEFAULT_PORTFOLIO_URL =
  process.env.NEXT_PUBLIC_PORTFOLIO_APP_URL ?? "http://127.0.0.1:8501";

type PortfolioReturnContext = {
  portfolio: string | null;
  user: string | null;
  resume: string | null;
};

function sanitizePortfolioOrigin(raw: string): string | null {
  try {
    const url = new URL(raw);
    if (url.protocol === "http:" || url.protocol === "https:") {
      return url.origin;
    }
  } catch {
    return null;
  }

  return null;
}

function configuredPortfolioOrigin(): string | null {
  if (!process.env.NEXT_PUBLIC_PORTFOLIO_APP_URL) {
    return null;
  }

  return sanitizePortfolioOrigin(process.env.NEXT_PUBLIC_PORTFOLIO_APP_URL);
}

export function isPortfolioAppOrigin(origin: string): boolean {
  const sanitized = sanitizePortfolioOrigin(origin);
  if (!sanitized) {
    return false;
  }

  const configured = configuredPortfolioOrigin();
  if (configured && configured === sanitized) {
    return true;
  }

  try {
    const url = new URL(sanitized);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return false;
    }

    return url.hostname === "localhost" || url.hostname === "127.0.0.1";
  } catch {
    return false;
  }
}

export function rememberPortfolioReturn(context: PortfolioReturnContext): void {
  if (typeof window === "undefined") {
    return;
  }

  if (context.portfolio) {
    const origin = sanitizePortfolioOrigin(context.portfolio);
    if (origin) {
      sessionStorage.setItem(STORAGE_KEY, origin);
    }
  }

  if (context.user) {
    sessionStorage.setItem(STORAGE_USER_KEY, context.user);
  }

  if (context.resume) {
    sessionStorage.setItem(STORAGE_RESUME_KEY, context.resume);
  }
}

export function readStoredPortfolioOrigin(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const stored = sessionStorage.getItem(STORAGE_KEY);
  if (!stored || !isPortfolioAppOrigin(stored)) {
    return null;
  }

  return stored;
}

function readStoredReturnContext(): PortfolioReturnContext {
  if (typeof window === "undefined") {
    return { portfolio: null, user: null, resume: null };
  }

  return {
    portfolio: readStoredPortfolioOrigin(),
    user: sessionStorage.getItem(STORAGE_USER_KEY),
    resume: sessionStorage.getItem(STORAGE_RESUME_KEY),
  };
}

export function portfolioOriginFromReferrer(referrer: string): string | null {
  try {
    const url = new URL(referrer);
    if (isPortfolioAppOrigin(url.origin)) {
      return url.origin;
    }
  } catch {
    return null;
  }

  return null;
}

function resolvePortfolioOrigin(raw: string | null): string {
  if (typeof document !== "undefined") {
    const fromReferrer = portfolioOriginFromReferrer(document.referrer);
    if (fromReferrer) {
      return fromReferrer;
    }
  }

  if (raw) {
    const fromParam = sanitizePortfolioOrigin(raw);
    if (fromParam) {
      return fromParam;
    }
  }

  const stored = readStoredPortfolioOrigin();
  if (stored) {
    return stored;
  }

  return DEFAULT_PORTFOLIO_URL;
}

export function resolvePortfolioHref(context: PortfolioReturnContext): string {
  const stored = readStoredReturnContext();
  const origin = resolvePortfolioOrigin(context.portfolio ?? stored.portfolio);
  const user = context.user ?? stored.user;
  const resume = context.resume ?? stored.resume;
  const target = new URL(origin);

  if (user) {
    target.searchParams.set("user", user);
  }

  if (resume) {
    target.searchParams.set("resume", resume);
  }

  return target.toString();
}
