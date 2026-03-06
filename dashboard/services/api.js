const reportUrl = import.meta.env.VITE_REPORT_JSON_URL?.trim();
const reportBase = import.meta.env.VITE_REPORT_BASE_URL?.trim();

export class ReportFetchError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "ReportFetchError";
    this.status = options.status;
    this.url = options.url;
    this.code = options.code || "REPORT_FETCH_ERROR";
  }
}

function resolveReportUrl() {
  if (reportUrl) {
    return reportUrl;
  }
  if (reportBase) {
    return `${reportBase.replace(/\/$/, "")}/latest/report.json`;
  }
  return "/report.json";
}

export async function fetchLatestReport() {
  const url = resolveReportUrl();
  let response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new ReportFetchError("Unable to reach report endpoint. Check network or CORS configuration.", {
      url,
      code: "NETWORK_ERROR",
    });
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new ReportFetchError("No report is available yet. Run the backend job and refresh.", {
        status: response.status,
        url,
        code: "REPORT_NOT_FOUND",
      });
    }
    throw new ReportFetchError(`Failed to fetch report (${response.status}) from ${url}`, {
      status: response.status,
      url,
      code: "HTTP_ERROR",
    });
  }

  try {
    return await response.json();
  } catch {
    throw new ReportFetchError("Report endpoint returned invalid JSON.", {
      status: response.status,
      url,
      code: "INVALID_JSON",
    });
  }
}
