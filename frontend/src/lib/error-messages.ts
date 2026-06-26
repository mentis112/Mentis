import i18n from "@/i18n";

type ErrorDetails = Record<string, unknown>;

export class ApiRequestError extends Error {
  code?: string;
  status?: number;
  details?: ErrorDetails;
  rawMessage: string;

  constructor(params: {
    message: string;
    rawMessage: string;
    code?: string;
    status?: number;
    details?: ErrorDetails;
  }) {
    super(params.message);
    this.name = "ApiRequestError";
    this.code = params.code;
    this.status = params.status;
    this.details = params.details;
    this.rawMessage = params.rawMessage;
  }
}

type UserFacingMessageParams = {
  rawMessage?: string | null;
  code?: string;
  status?: number;
};

function translate(key: string) {
  const translated = i18n.t(key);
  return typeof translated === "string" ? translated : key;
}

function normalize(message?: string | null) {
  return (message || "").trim().toLowerCase();
}

function includesAny(message: string, patterns: string[]) {
  return patterns.some((pattern) => message.includes(pattern));
}

function mapRawMessageToFriendlyText(rawMessage?: string | null) {
  const message = normalize(rawMessage);
  if (!message) {
    return null;
  }

  if (includesAny(message, ["failed to fetch", "networkerror", "unable to connect", "load failed"])) {
    return translate("errors.network.unreachable");
  }
  if (includesAny(message, ["unauthorized", "authentication failed", "invalid refresh token"])) {
    return translate("errors.auth.sessionExpired");
  }
  if (includesAny(message, ["forbidden", "authorization failed"])) {
    return translate("errors.auth.forbidden");
  }
  if (includesAny(message, ["submission not found", "provider configuration not found", "assignment group not found", "evaluation result not found", "resource not found"])) {
    return translate("errors.data.notFound");
  }
  if (includesAny(message, ["conflict", "duplicate submission detected"])) {
    return translate("errors.data.conflict");
  }
  if (
    includesAny(message, [
      "student id overrides",
      "must be a json object",
      "valid dictionary or object",
      "invalid request",
      "unprocessable entity",
    ])
  ) {
    return translate("errors.validation.invalidRequest");
  }
  if (includesAny(message, ["student id is required", "enter a student id"])) {
    return translate("errors.validation.studentIdRequired");
  }
  if (
    includesAny(message, [
      "student id must contain digits only",
      "at least 5 digits",
    ])
  ) {
    return translate("submissions.studentIdDigitsOnlyMinLength");
  }
  if (includesAny(message, ["must have a student id before evaluation", "before evaluation"])) {
    return translate("errors.validation.studentIdBeforeEvaluation");
  }
  if (
    includesAny(message, [
      "content is not ready for evaluation",
      "did not produce readable content",
      "uploaded file did not produce readable content",
      "the selected file could not be read",
    ])
  ) {
    return translate("errors.validation.contentNotReady");
  }
  if (includesAny(message, ["no evaluatable submissions were found", "no evaluatable items are available"])) {
    return translate("errors.validation.noEvaluatable");
  }
  if (includesAny(message, ["at least one file is required"])) {
    return translate("errors.validation.missingFiles");
  }
  if (includesAny(message, ["upload batch exceeds the configured file limit", "too many files"])) {
    return translate("errors.upload.tooManyFiles");
  }
  if (includesAny(message, ["file exceeds the configured size limit", "inside zip exceeds the configured size limit"])) {
    return translate("errors.upload.fileTooLarge");
  }
  if (includesAny(message, ["unsupported file inside zip archive", "unsupported file type"])) {
    return translate("errors.upload.unsupportedFile");
  }
  if (includesAny(message, ["zip archive is empty"])) {
    return translate("errors.upload.emptyArchive");
  }
  if (includesAny(message, ["zip archive does not contain supported files"])) {
    return translate("errors.upload.noSupportedFilesInArchive");
  }
  if (includesAny(message, ["corrupted or unsupported zip archive", "failed to read zip archive"])) {
    return translate("errors.upload.invalidArchive");
  }
  if (
    includesAny(message, [
      "duplicate file content in this upload batch",
      "duplicate filename in this upload batch",
      "duplicate student id",
    ]) &&
    message.includes("upload batch")
  ) {
    return translate("errors.upload.duplicateInBatch");
  }
  if (includesAny(message, ["existing submission in this group", "already uploaded existing submission"])) {
    return translate("errors.upload.alreadyUploaded");
  }
  if (includesAny(message, ["no active ai provider configuration is available"])) {
    return translate("errors.provider.notConfigured");
  }
  if (includesAny(message, ["ollama is reachable, but model", "ollama pull"])) {
    return translate("errors.provider.modelUnavailable");
  }
  if (
    includesAny(message, [
      "make sure ollama is running",
      "ollama connection failed",
      "ollama evaluation request failed",
    ])
  ) {
    return translate("errors.provider.ollamaUnavailable");
  }
  if (includesAny(message, ["request is too large", "too large for this model", "payload too large"])) {
    return translate("errors.provider.requestTooLarge");
  }
  if (includesAny(message, ["prompt exceeds provider limits", "token limit"])) {
    return translate("errors.provider.promptTooLarge");
  }
  if (includesAny(message, ["rate limit", "too many requests", "(429)", " 429"])) {
    return translate("errors.provider.rateLimit");
  }
  if (includesAny(message, ["timed out", "timeout"])) {
    return translate("errors.provider.timeout");
  }
  if (
    includesAny(message, [
      "returned feedback without numeric scores",
      "did not contain parsable content",
      "criterion_scores array",
      "summary_feedback",
      "numeric scores",
      "parsable content",
    ])
  ) {
    return translate("errors.provider.invalidResponse");
  }
  if (includesAny(message, ["connection failed", "unable to reach provider", "provider is unavailable"])) {
    return translate("errors.provider.connectionFailed");
  }
  if (includesAny(message, ["evaluation cancelled by instructor"])) {
    return translate("errors.evaluation.cancelled");
  }

  return null;
}

function mapCodeToFriendlyText({ code, status, rawMessage }: UserFacingMessageParams) {
  const byRaw = mapRawMessageToFriendlyText(rawMessage);
  if (byRaw) {
    return byRaw;
  }

  switch (code) {
    case "network_error":
      return translate("errors.network.unreachable");
    case "authentication_error":
      return translate("errors.auth.sessionExpired");
    case "authorization_error":
      return translate("errors.auth.forbidden");
    case "not_found":
      return translate("errors.data.notFound");
    case "conflict_error":
      return translate("errors.data.conflict");
    case "validation_error":
      return translate("errors.validation.invalidRequest");
    case "external_service_error":
      return translate("errors.provider.connectionFailed");
    case "rate_limit_exceeded":
      return translate("errors.provider.rateLimit");
    case "internal_server_error":
      return translate("errors.server.unexpected");
    default:
      if (status === 401) {
        return translate("errors.auth.sessionExpired");
      }
      if (status === 403) {
        return translate("errors.auth.forbidden");
      }
      if (status === 404) {
        return translate("errors.data.notFound");
      }
      if (status === 409) {
        return translate("errors.data.conflict");
      }
      if (status != null && status >= 500) {
        return translate("errors.server.unexpected");
      }
      return null;
  }
}

export function resolveUserFacingMessage(params: UserFacingMessageParams) {
  return (
    mapCodeToFriendlyText(params) ||
    mapRawMessageToFriendlyText(params.rawMessage) ||
    translate("errors.generic")
  );
}

export function createApiRequestError(params: {
  rawMessage?: string | null;
  code?: string;
  status?: number;
  details?: ErrorDetails;
}) {
  const rawMessage = params.rawMessage?.trim() || "";
  return new ApiRequestError({
    message: resolveUserFacingMessage({
      rawMessage,
      code: params.code,
      status: params.status,
    }),
    rawMessage,
    code: params.code,
    status: params.status,
    details: params.details,
  });
}

export function getUserFacingErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    return error.message;
  }
  if (error instanceof Error) {
    return mapRawMessageToFriendlyText(error.message) || error.message || translate("errors.generic");
  }
  return translate("errors.generic");
}

export function getUserFacingReason(message?: string | null, fallbackKey = "errors.generic") {
  if (!message?.trim()) {
    return translate("common.notAvailable");
  }
  return mapRawMessageToFriendlyText(message) || translate(fallbackKey);
}
