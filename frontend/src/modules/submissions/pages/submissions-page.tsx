import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Trash2, UploadCloud } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import * as XLSX from "xlsx";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/shared/badge";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { EmptyState } from "@/components/shared/empty-state";
import { Input } from "@/components/shared/input";
import { PaginationControls } from "@/components/shared/pagination-controls";
import {
  getUserFacingErrorMessage,
  getUserFacingReason,
} from "@/lib/error-messages";
import { Select } from "@/components/shared/select";
import {
  cancelBatchEvaluations,
  fetchBatchEvaluationStatus,
  startBatchEvaluations,
} from "@/services/evaluations";
import { fetchGroups } from "@/services/groups";
import {
  canEvaluateSubmission,
  fetchEvaluatableSubmissionIds,
  fetchSubmissionReport,
  fetchSubmissions,
  previewSubmissionStudentIds,
  updateSubmissionStudentId,
  uploadSubmissions,
} from "@/services/submissions";
import type { Submission, SubmissionReportRow } from "@/types/api";

const DEFAULT_PAGE_SIZE = 25;
const STUDENT_ID_PATTERN = /^\d{5,}$/;

const normalizeStudentIdInput = (value: string) => value.replace(/\D/g, "");

const isValidManualStudentId = (value: string) =>
  STUDENT_ID_PATTERN.test(value.trim());

type FilePreviewRow = {
  localKey: string;
  original_filename: string;
  source_upload_index: number | null;
  source_upload_filename: string | null;
  from_archive: boolean;
  student_id: string | null;
  accepted: boolean;
  reason: string | null;
  needs_student_id: boolean;
  is_duplicate: boolean;
  duplicate_reasons: string[];
  has_existing_match: boolean;
  existing_duplicate_reasons: string[];
  existing_submission_id: string | null;
  existing_submission_evaluated: boolean;
};

const getStatusBadgeColor = (status: string) => {
  switch (status) {
    case "completed":
    case "evaluated":
      return "bg-emerald-500/15 text-emerald-700 border-emerald-500/20 dark:text-emerald-400";
    case "failed":
      return "bg-destructive/15 text-destructive border-destructive/20";
    case "pending":
    case "queued":
      return "bg-amber-500/15 text-amber-700 border-amber-500/20 dark:text-amber-400";
    case "processing":
    case "partially_processed":
      return "bg-blue-500/15 text-blue-700 border-blue-500/20 dark:text-blue-400";
    default:
      return "";
  }
};

export function SubmissionPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [groupId, setGroupId] = useState(
    () => sessionStorage.getItem("activeGroupId") || "",
  );

  useEffect(() => {
    if (groupId) {
      sessionStorage.setItem("activeGroupId", groupId);
    } else {
      sessionStorage.removeItem("activeGroupId");
    }
  }, [groupId]);

  const [files, setFiles] = useState<File[]>([]);
  const [excludedArchiveEntries, setExcludedArchiveEntries] = useState<
    string[]
  >([]);
  const [studentIdDrafts, setStudentIdDrafts] = useState<
    Record<string, string>
  >({});
  const [previewRows, setPreviewRows] = useState<FilePreviewRow[]>([]);
  const [approvedExistingDuplicateKeys, setApprovedExistingDuplicateKeys] =
    useState<string[]>([]);
  const [evaluateAfterUpload, setEvaluateAfterUpload] = useState(true);
  const [queueingIds, setQueueingIds] = useState<string[]>([]);
  const [reportSearch, setReportSearch] = useState("");
  const [submissionsPage, setSubmissionsPage] = useState(1);
  const [submissionsPageSize, setSubmissionsPageSize] =
    useState(DEFAULT_PAGE_SIZE);
  const [reportPage, setReportPage] = useState(1);
  const [reportPageSize, setReportPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [missingStudentPage, setMissingStudentPage] = useState(1);
  const [missingStudentPageSize, setMissingStudentPageSize] =
    useState(DEFAULT_PAGE_SIZE);
  const [fileInputKey, setFileInputKey] = useState(0);
  const wasBatchActiveRef = useRef(false);

  const groupsQuery = useQuery({ queryKey: ["groups"], queryFn: fetchGroups });
  const submissionsQuery = useQuery({
    queryKey: [
      "submissions",
      groupId,
      "page",
      submissionsPage,
      submissionsPageSize,
    ],
    queryFn: () =>
      fetchSubmissions({
        groupId,
        page: submissionsPage,
        pageSize: submissionsPageSize,
      }),
    enabled: Boolean(groupId),
  });
  const missingStudentQuery = useQuery({
    queryKey: [
      "submissions",
      groupId,
      "missing-student",
      missingStudentPage,
      missingStudentPageSize,
    ],
    queryFn: () =>
      fetchSubmissions({
        groupId,
        page: missingStudentPage,
        pageSize: missingStudentPageSize,
        missingStudentIdOnly: true,
      }),
    enabled: Boolean(groupId),
  });
  const evaluatableSubmissionIdsQuery = useQuery({
    queryKey: ["submissions", groupId, "evaluatable-ids"],
    queryFn: () => fetchEvaluatableSubmissionIds(groupId),
    enabled: Boolean(groupId),
  });
  const reportQuery = useQuery({
    queryKey: [
      "submission-report",
      groupId,
      reportSearch,
      reportPage,
      reportPageSize,
    ],
    queryFn: () =>
      fetchSubmissionReport({
        groupId,
        search: reportSearch,
        page: reportPage,
        pageSize: reportPageSize,
      }),
    enabled: Boolean(groupId),
  });
  const batchStatusQuery = useQuery({
    queryKey: ["evaluation-batch-status"],
    queryFn: fetchBatchEvaluationStatus,
    refetchInterval: (query) => (query.state.data?.active ? 2000 : false),
    refetchIntervalInBackground: true,
  });
  const selectedGroup = groupsQuery.data?.find((group) => group.id === groupId);
  const batchStatus = batchStatusQuery.data;
  const isBatchActive = Boolean(batchStatus?.active);
  const submissionRows = submissionsQuery.data?.items ?? [];
  const submissionsTotal = groupId ? (submissionsQuery.data?.total ?? 0) : 0;
  const missingStudentIdSubmissions = missingStudentQuery.data?.items ?? [];
  const missingStudentTotal = groupId
    ? (missingStudentQuery.data?.total ?? 0)
    : 0;
  const reportRows = reportQuery.data?.items ?? [];
  const reportTotal = groupId ? (reportQuery.data?.total ?? 0) : 0;
  const formatFailureMessage = (message?: string | null) => {
    if (!message?.trim()) {
      return t("common.notAvailable");
    }
    return message.length > 220 ? `${message.slice(0, 220)}…` : message;
  };
  const duplicatePreviewRows = useMemo(
    () => previewRows.filter((row) => row.is_duplicate),
    [previewRows],
  );
  const existingDuplicatePreviewRows = useMemo(
    () => previewRows.filter((row) => row.has_existing_match),
    [previewRows],
  );
  const unresolvedExistingDuplicateRows = useMemo(
    () =>
      existingDuplicatePreviewRows.filter(
        (row) => !approvedExistingDuplicateKeys.includes(row.localKey),
      ),
    [approvedExistingDuplicateKeys, existingDuplicatePreviewRows],
  );
  const unsupportedPreviewRows = useMemo(
    () =>
      previewRows.filter(
        (row) => !row.accepted && !row.is_duplicate && !row.has_existing_match,
      ),
    [previewRows],
  );
  const getDistinctFriendlyReasons = (
    reasons: string[],
    fallbackKey = "errors.generic",
  ) =>
    Array.from(
      new Set(
        reasons.map((reason) => getUserFacingReason(reason, fallbackKey)),
      ),
    );
  const evaluatableSubmissionIds = useMemo(
    () => evaluatableSubmissionIdsQuery.data?.items ?? [],
    [evaluatableSubmissionIdsQuery.data],
  );
  const currentBatchSubmission = useMemo(
    () =>
      submissionRows.find(
        (submission) => submission.id === batchStatus?.current_submission_id,
      ) ?? null,
    [submissionRows, batchStatus?.current_submission_id],
  );
  const batchProgressPercent = useMemo(() => {
    if (!batchStatus?.total_count) {
      return 0;
    }
    return Math.round(
      (batchStatus.processed_count / batchStatus.total_count) * 100,
    );
  }, [batchStatus?.processed_count, batchStatus?.total_count]);
  const reportCriterionNames = useMemo(
    () => selectedGroup?.criteria?.map((criterion) => criterion.name) ?? [],
    [selectedGroup?.criteria],
  );
  const [activeCriterionTab, setActiveCriterionTab] = useState("");
  const invalidateLiveQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["submissions"] }),
      queryClient.invalidateQueries({ queryKey: ["submission-report"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["provider-usage-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["all-evaluations"] }),
      queryClient.invalidateQueries({ queryKey: ["groups"] }),
    ]);
  };

  useEffect(() => {
    if (!reportCriterionNames.length) {
      setActiveCriterionTab("");
      return;
    }
    if (!reportCriterionNames.includes(activeCriterionTab)) {
      setActiveCriterionTab(reportCriterionNames[0]);
    }
  }, [reportCriterionNames, activeCriterionTab]);

  useEffect(() => {
    setSubmissionsPage(1);
    setMissingStudentPage(1);
  }, [groupId]);

  useEffect(() => {
    setReportSearch("");
  }, [groupId]);

  useEffect(() => {
    setReportPage(1);
  }, [groupId, reportSearch]);

  useEffect(() => {
    const totalPages = Math.max(
      1,
      Math.ceil(submissionsTotal / submissionsPageSize),
    );
    if (submissionsPage > totalPages) {
      setSubmissionsPage(totalPages);
    }
  }, [submissionsPage, submissionsPageSize, submissionsTotal]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(reportTotal / reportPageSize));
    if (reportPage > totalPages) {
      setReportPage(totalPages);
    }
  }, [reportPage, reportPageSize, reportTotal]);

  useEffect(() => {
    const totalPages = Math.max(
      1,
      Math.ceil(missingStudentTotal / missingStudentPageSize),
    );
    if (missingStudentPage > totalPages) {
      setMissingStudentPage(totalPages);
    }
  }, [missingStudentPage, missingStudentPageSize, missingStudentTotal]);

  useEffect(() => {
    const isCurrentlyActive = Boolean(batchStatus?.active);
    if (isCurrentlyActive) {
      void invalidateLiveQueries();
    }
    if (wasBatchActiveRef.current && !isCurrentlyActive) {
      void invalidateLiveQueries();
    }
    wasBatchActiveRef.current = isCurrentlyActive;
  }, [
    batchStatus?.active,
    batchStatus?.completed_count,
    batchStatus?.failed_count,
    batchStatus?.processed_count,
  ]);

  const previewMutation = useMutation({
    mutationFn: previewSubmissionStudentIds,
    onSuccess: (payload) => {
      setPreviewRows(
        payload.results.map((result, index) => ({
          localKey: `${result.source_upload_index ?? index}:${index}:${result.original_filename}`,
          original_filename: result.original_filename,
          source_upload_index: result.source_upload_index ?? null,
          source_upload_filename: result.source_upload_filename ?? null,
          from_archive: Boolean(result.from_archive),
          student_id: result.student_id ?? null,
          accepted: result.accepted,
          reason: result.reason ?? null,
          needs_student_id: Boolean(result.needs_student_id),
          is_duplicate: Boolean(result.is_duplicate),
          duplicate_reasons: result.duplicate_reasons ?? [],
          has_existing_match: Boolean(result.has_existing_match),
          existing_duplicate_reasons: result.existing_duplicate_reasons ?? [],
          existing_submission_id: result.existing_submission_id ?? null,
          existing_submission_evaluated: Boolean(
            result.existing_submission_evaluated,
          ),
        })),
      );
      const duplicates = payload.results.filter(
        (result) => result.is_duplicate,
      );
      if (duplicates.length) {
        toast.error(
          t("submissions.duplicateFilesDetected", { count: duplicates.length }),
        );
      }
    },
    onError: (error: Error) => {
      setPreviewRows([]);
      toast.error(getUserFacingErrorMessage(error));
    },
  });

  const startBatchMutation = useMutation({
    mutationFn: startBatchEvaluations,
  });
  const cancelBatchMutation = useMutation({
    mutationFn: cancelBatchEvaluations,
    onSuccess: async (payload) => {
      if (!payload.was_active) {
        toast.error(t("submissions.batchNotActive"));
      } else {
        toast.success(t("submissions.batchCancelRequested"));
      }
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["evaluation-batch-status"],
        }),
        invalidateLiveQueries(),
      ]);
    },
    onError: (error: Error) => {
      toast.error(getUserFacingErrorMessage(error));
    },
  });

  const queueEvaluations = async (submissionIds: string[]) => {
    if (!submissionIds.length) {
      toast.error(t("submissions.noEvaluatableSubmissions"));
      return;
    }
    try {
      const result = await startBatchMutation.mutateAsync(submissionIds);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["evaluation-batch-status"],
        }),
        invalidateLiveQueries(),
      ]);
      if (result.already_running) {
        toast.error(t("submissions.batchAlreadyRunning"));
        return;
      }
      toast.success(
        t("submissions.batchQueued", { count: result.queued_count }),
      );
    } catch (error) {
      void invalidateLiveQueries();
      toast.error(getUserFacingErrorMessage(error));
    }
  };

  const uploadMutation = useMutation({
    mutationFn: uploadSubmissions,
    onSuccess: async (payload) => {
      setFiles([]);
      setPreviewRows([]);
      setExcludedArchiveEntries([]);
      setStudentIdDrafts({});
      setApprovedExistingDuplicateKeys([]);
      setFileInputKey((current) => current + 1);
      await invalidateLiveQueries();
      toast.success(t("submissions.upload"));
      const deferredStudentIdCount = payload.results.filter(
        (result) => result.accepted && !result.student_id?.trim(),
      ).length;
      if (deferredStudentIdCount) {
        toast(
          t("submissions.missingStudentIdsDeferredNotice", {
            count: deferredStudentIdCount,
          }),
        );
      }
      const readySubmissionIds = payload.results
        .filter(
          (result) =>
            result.accepted &&
            result.status === "pending" &&
            Boolean(result.student_id?.trim()) &&
            result.submission_id,
        )
        .map((result) => result.submission_id as string);
      if (evaluateAfterUpload && readySubmissionIds.length) {
        await queueEvaluations(readySubmissionIds);
      }
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const saveStudentIdMutation = useMutation({
    mutationFn: ({
      submissionId,
      studentId,
    }: {
      submissionId: string;
      studentId: string;
    }) => updateSubmissionStudentId(submissionId, studentId),
    onSuccess: (_, variables) => {
      setStudentIdDrafts((current) => {
        const next = { ...current };
        delete next[variables.submissionId];
        return next;
      });
      void invalidateLiveQueries();
      toast.success(t("submissions.studentIdSaved"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const evaluateMutation = useMutation({
    mutationFn: async (submissionId: string) => {
      setQueueingIds((current) =>
        Array.from(new Set([...current, submissionId])),
      );
      try {
        await queueEvaluations([submissionId]);
      } finally {
        setQueueingIds((current) =>
          current.filter((item) => item !== submissionId),
        );
      }
      return submissionId;
    },
  });

  const evaluateAllMutation = useMutation({
    mutationFn: async () => {
      await queueEvaluations(evaluatableSubmissionIds);
    },
  });
  const isEvaluateAllBusy =
    startBatchMutation.isPending ||
    evaluateAllMutation.isPending ||
    evaluatableSubmissionIdsQuery.isFetching;
  const evaluateAllButtonLabel = cancelBatchMutation.isPending
    ? t("common.loading")
    : batchStatus?.cancel_requested
      ? t("submissions.batchCancelPending")
      : isBatchActive
        ? t("submissions.stopBatch")
        : isEvaluateAllBusy
          ? t("common.loading")
          : t("submissions.evaluateAll");

  const handleEvaluateAllClick = () => {
    if (isBatchActive) {
      cancelBatchMutation.mutate();
      return;
    }
    evaluateAllMutation.mutate();
  };
  const getSubmissionActionState = (submission: Submission) => {
    if (queueingIds.includes(submission.id)) {
      return {
        label: t("common.loading"),
        disabled: true,
        variant: "primary" as const,
      };
    }

    if (submission.status === "failed") {
      return {
        label: t("evaluations.reEvaluate"),
        disabled: false,
        variant: "primary" as const,
      };
    }

    if (submission.status === "pending") {
      return {
        label: t("submissions.evaluateNow"),
        disabled: false,
        variant: "primary" as const,
      };
    }

    if (submission.status === "queued") {
      return {
        label: isBatchActive ? t("state.queued") : t("evaluations.reEvaluate"),
        disabled: isBatchActive,
        variant: "secondary" as const,
      };
    }

    if (
      submission.status === "processing" ||
      submission.status === "partially_processed"
    ) {
      return {
        label: t(`state.${submission.status}`),
        disabled: true,
        variant: "secondary" as const,
      };
    }

    return null;
  };

  const submitUpload = () => {
    if (!groupId || !files.length) {
      toast.error(t("submissions.upload"));
      return;
    }
    const invalidStudentIdDraft = previewRows.find((row) => {
      const draft = studentIdDrafts[row.localKey]?.trim();
      return Boolean(draft) && !isValidManualStudentId(draft || "");
    });
    if (invalidStudentIdDraft) {
      toast.error(t("submissions.studentIdDigitsOnlyMinLength"));
      return;
    }
    if (duplicatePreviewRows.length) {
      toast.error(t("submissions.removeDuplicatesBeforeUpload"));
      return;
    }
    if (unresolvedExistingDuplicateRows.length) {
      toast.error(t("submissions.resolveExistingDuplicatesBeforeUpload"));
      return;
    }
    if (unsupportedPreviewRows.length) {
      toast.error(t("submissions.removeUnsupportedBeforeUpload"));
      return;
    }
    if (
      evaluateAfterUpload &&
      selectedGroup &&
      !selectedGroup.ready_for_evaluation
    ) {
      toast.error(
        t("submissions.groupNotReady", {
          total: selectedGroup.weights_total ?? 0,
          gradeScale: selectedGroup.grade_scale,
          criteriaCount: selectedGroup.criteria?.length ?? 0,
        }),
      );
      return;
    }
    const formData = new FormData();
    formData.append("group_id", groupId);
    files.forEach((file) => {
      formData.append("files", file);
    });
    excludedArchiveEntries.forEach((entry) =>
      formData.append("excluded_archive_entries", entry),
    );
    previewRows
      .filter((row) => approvedExistingDuplicateKeys.includes(row.localKey))
      .forEach((row) =>
        formData.append("allowed_existing_duplicates", row.original_filename),
      );
    const studentIdOverrides = Object.fromEntries(
      previewRows
        .map((row) => [
          row.original_filename,
          studentIdDrafts[row.localKey]?.trim(),
        ])
        .filter((entry): entry is [string, string] => Boolean(entry[1])),
    );
    if (Object.keys(studentIdOverrides).length) {
      formData.append(
        "student_id_overrides_json",
        JSON.stringify(studentIdOverrides),
      );
    }
    const studentIdsToSend =
      previewRows.length === files.length
        ? previewRows.map(
            (row) =>
              studentIdDrafts[row.localKey]?.trim() || row.student_id || "",
          )
        : files.map(() => "");
    studentIdsToSend.forEach((id) => formData.append("student_ids", id));
    uploadMutation.mutate(formData);
  };

  const handleSaveStudentId = (submissionId: string) => {
    const studentId = (studentIdDrafts[submissionId] || "").trim();
    if (!studentId) {
      toast.error(t("submissions.studentIdRequired"));
      return;
    }
    if (!isValidManualStudentId(studentId)) {
      toast.error(t("submissions.studentIdDigitsOnlyMinLength"));
      return;
    }
    saveStudentIdMutation.mutate({ submissionId, studentId });
  };

  const triggerPreview = (
    nextFiles: File[],
    nextGroupId: string,
    nextExcludedEntries: string[] = excludedArchiveEntries,
  ) => {
    if (!nextFiles.length) {
      setPreviewRows([]);
      return;
    }
    const formData = new FormData();
    if (nextGroupId) {
      formData.append("group_id", nextGroupId);
    }
    nextFiles.forEach((file) => {
      formData.append("files", file);
    });
    nextExcludedEntries.forEach((entry) =>
      formData.append("excluded_archive_entries", entry),
    );
    previewMutation.mutate(formData);
  };

  const handleFilesSelected = (nextFiles: FileList | null) => {
    const normalizedFiles = nextFiles ? Array.from(nextFiles) : [];
    const mergedFiles = [...files, ...normalizedFiles];
    setFiles(mergedFiles);
    setPreviewRows([]);
    setStudentIdDrafts({});
    setApprovedExistingDuplicateKeys([]);
    setExcludedArchiveEntries([]);
    triggerPreview(mergedFiles, groupId, []);
  };

  const handleRemovePreviewFile = (rowKey: string) => {
    const rowToRemove = previewRows.find((row) => row.localKey === rowKey);
    if (!rowToRemove) {
      return;
    }
    if (rowToRemove.from_archive) {
      const sourceIndex = rowToRemove.source_upload_index;
      const removedSourceFilename = rowToRemove.source_upload_filename || "";
      const rowsFromSameSource = previewRows.filter(
        (row) => row.source_upload_index === sourceIndex,
      );
      if (
        sourceIndex != null &&
        sourceIndex >= 0 &&
        sourceIndex < files.length &&
        rowsFromSameSource.length <= 1
      ) {
        const nextFiles = files.filter((_, index) => index !== sourceIndex);
        const nextExcludedEntries = excludedArchiveEntries.filter(
          (entry) =>
            !removedSourceFilename ||
            !entry.startsWith(`${removedSourceFilename}::`),
        );
        setFiles(nextFiles);
        setExcludedArchiveEntries(nextExcludedEntries);
        setStudentIdDrafts((current) => {
          const next = { ...current };
          previewRows
            .filter((row) => row.source_upload_index === sourceIndex)
            .forEach((row) => {
              delete next[row.localKey];
            });
          return next;
        });
        setApprovedExistingDuplicateKeys((current) =>
          current.filter(
            (key) =>
              !previewRows.some(
                (row) =>
                  row.source_upload_index === sourceIndex &&
                  row.localKey === key,
              ),
          ),
        );
        setFileInputKey((current) => current + 1);
        triggerPreview(nextFiles, groupId, nextExcludedEntries);
        return;
      }
      const nextExcludedEntries = Array.from(
        new Set([...excludedArchiveEntries, rowToRemove.original_filename]),
      );
      setExcludedArchiveEntries(nextExcludedEntries);
      setStudentIdDrafts((current) => {
        const next = { ...current };
        delete next[rowKey];
        return next;
      });
      setApprovedExistingDuplicateKeys((current) =>
        current.filter((key) => key !== rowKey),
      );
      triggerPreview(files, groupId, nextExcludedEntries);
      return;
    }
    const sourceIndex = rowToRemove.source_upload_index;
    if (sourceIndex == null || sourceIndex < 0 || sourceIndex >= files.length) {
      return;
    }
    const nextFiles = files.filter((_, index) => index !== sourceIndex);
    const removedSourceFilename = rowToRemove.source_upload_filename || "";
    const nextExcludedEntries = excludedArchiveEntries.filter(
      (entry) =>
        !removedSourceFilename ||
        !entry.startsWith(`${removedSourceFilename}::`),
    );
    setFiles(nextFiles);
    setExcludedArchiveEntries(nextExcludedEntries);
    setStudentIdDrafts((current) => {
      const next = { ...current };
      previewRows
        .filter((row) => row.source_upload_index === sourceIndex)
        .forEach((row) => {
          delete next[row.localKey];
        });
      return next;
    });
    setApprovedExistingDuplicateKeys((current) =>
      current.filter((key) => key !== rowKey),
    );
    setFileInputKey((current) => current + 1);
    triggerPreview(nextFiles, groupId, nextExcludedEntries);
  };

  const removePreviewRowsFromUpload = (rowsToRemove: FilePreviewRow[]) => {
    if (!rowsToRemove.length) {
      return;
    }

    const rowKeysToRemove = new Set(rowsToRemove.map((row) => row.localKey));
    const sourceIndexesToRemove = new Set<number>();
    const archiveEntriesToExclude = new Set(excludedArchiveEntries);

    rowsToRemove.forEach((row) => {
      const sourceIndex = row.source_upload_index;
      if (
        sourceIndex == null ||
        sourceIndex < 0 ||
        sourceIndex >= files.length
      ) {
        return;
      }

      if (!row.from_archive) {
        sourceIndexesToRemove.add(sourceIndex);
        return;
      }

      const rowsFromSameSource = previewRows.filter(
        (candidate) => candidate.source_upload_index === sourceIndex,
      );
      const removeWholeSource = rowsFromSameSource.every((candidate) =>
        rowKeysToRemove.has(candidate.localKey),
      );

      if (removeWholeSource) {
        sourceIndexesToRemove.add(sourceIndex);
        return;
      }

      archiveEntriesToExclude.add(row.original_filename);
    });

    const removedSourceRows = previewRows.filter(
      (row) =>
        row.source_upload_index != null &&
        sourceIndexesToRemove.has(row.source_upload_index),
    );
    const removedRowKeys = new Set([
      ...rowKeysToRemove,
      ...removedSourceRows.map((row) => row.localKey),
    ]);
    const removedSourceFilenames = new Set(
      removedSourceRows
        .map((row) => row.source_upload_filename || "")
        .filter(Boolean),
    );

    const nextFiles = files.filter(
      (_, index) => !sourceIndexesToRemove.has(index),
    );
    const nextExcludedEntries = Array.from(archiveEntriesToExclude).filter(
      (entry) =>
        !Array.from(removedSourceFilenames).some((sourceFilename) =>
          entry.startsWith(`${sourceFilename}::`),
        ),
    );

    setFiles(nextFiles);
    setExcludedArchiveEntries(nextExcludedEntries);
    setStudentIdDrafts((current) => {
      const next = { ...current };
      removedRowKeys.forEach((key) => {
        delete next[key];
      });
      return next;
    });
    setApprovedExistingDuplicateKeys((current) =>
      current.filter((key) => !removedRowKeys.has(key)),
    );
    if (sourceIndexesToRemove.size) {
      setFileInputKey((current) => current + 1);
    }
    triggerPreview(nextFiles, groupId, nextExcludedEntries);
  };

  const handleRemoveAllUnsupportedPreviewFiles = () => {
    removePreviewRowsFromUpload(unsupportedPreviewRows);
  };

  const handleRemoveAllDuplicatePreviewFiles = () => {
    removePreviewRowsFromUpload(
      previewRows.filter((row) => row.is_duplicate || row.has_existing_match),
    );
  };

  useEffect(() => {
    if (files.length) {
      triggerPreview(files, groupId, excludedArchiveEntries);
    } else {
      setPreviewRows([]);
    }
  }, [groupId]);

  const renderCriterionResultForRow = (row: SubmissionReportRow) => {
    if (
      !row.latest_evaluation?.criterion_scores.length ||
      !activeCriterionTab
    ) {
      return (
        <span className="text-xs text-foreground/60">
          {t("submissions.noEvaluationYet")}
        </span>
      );
    }
    const score = row.latest_evaluation.criterion_scores.find(
      (item) => item.criterion_name === activeCriterionTab,
    );
    if (!score) {
      return (
        <span className="text-xs text-foreground/60">
          {t("submissions.noCriterionScore")}
        </span>
      );
    }
    const rawScore = score.manual_score ?? score.ai_score ?? 0;
    const percentage =
      row.grade_scale > 0 ? (rawScore / row.grade_scale) * 100 : 0;
    const points = (score.weight * percentage) / 100;
    return (
      <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1.5 whitespace-nowrap">
        <span className="font-medium">{score.criterion_name}</span>
        <span className="text-xs text-foreground/70">
          {t("submissions.criterionScoreFormat", {
            score: points.toFixed(2),
            weight: score.weight,
            percent: percentage.toFixed(1),
          })}
        </span>
      </div>
    );
  };

  const exportReportToExcel = async () => {
    if (!groupId || !reportTotal) {
      toast.error(t("submissions.noReportData"));
      return;
    }
    try {
      const exportPageSize = 500;
      const exportPages = Math.max(1, Math.ceil(reportTotal / exportPageSize));
      const exportItems: SubmissionReportRow[] = [];
      for (let page = 1; page <= exportPages; page += 1) {
        const exportPayload = await fetchSubmissionReport({
          groupId,
          search: reportSearch,
          page,
          pageSize: exportPageSize,
        });
        exportItems.push(...exportPayload.items);
      }
      const exportRows = exportItems.map((row) => {
        const criteriaMap = new Map(
          (row.latest_evaluation?.criterion_scores ?? []).map((score) => [
            score.criterion_name,
            score,
          ]),
        );
        const baseRow: Record<string, string | number> = {
          [t("common.filename")]: row.submission.original_filename,
          [t("common.studentId")]: row.submission.student_id || "",
          [t("common.status")]: t(`state.${row.submission.status}`),
          [t("submissions.totalAiScoreColumn")]:
            row.latest_evaluation?.total_ai_score ?? "",
          [t("evaluations.finalAdjusted")]:
            row.latest_evaluation?.final_adjusted_score ?? "",
          [t("groups.gradeScale")]: row.grade_scale,
        };
        reportCriterionNames.forEach((criterionName) => {
          const score = criteriaMap.get(criterionName);
          if (!score) {
            baseRow[
              `${criterionName} - ${t("submissions.scoreOutOfWeightColumn")}`
            ] = "";
            baseRow[`${criterionName} - ${t("submissions.percentageColumn")}`] =
              "";
            return;
          }
          const rawScore = score.manual_score ?? score.ai_score ?? 0;
          const percentage =
            row.grade_scale > 0 ? (rawScore / row.grade_scale) * 100 : 0;
          const points = (score.weight * percentage) / 100;
          baseRow[
            `${criterionName} - ${t("submissions.scoreOutOfWeightColumn")}`
          ] = Number(points.toFixed(2));
          baseRow[`${criterionName} - ${t("submissions.percentageColumn")}`] =
            Number(percentage.toFixed(1));
        });
        return baseRow;
      });
      const worksheet = XLSX.utils.json_to_sheet(exportRows);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Submissions");
      XLSX.writeFile(workbook, "submissions-report.xlsx");
    } catch (error) {
      toast.error(getUserFacingErrorMessage(error));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("submissions.title")}
        subtitle={t("submissions.subtitle")}
      />
      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="space-y-4 p-5">
          <div className="space-y-2">
            <label className="text-sm font-medium">
              {t("submissions.group")}
            </label>
            <Select
              value={groupId}
              onChange={(event) => setGroupId(event.target.value)}
            >
              <option value="">{t("common.notAvailable")}</option>
              {groupsQuery.data?.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.ready_for_evaluation
                    ? group.name
                    : `${group.name} (${t("submissions.notReadyLabel")})`}
                </option>
              ))}
            </Select>
            {selectedGroup ? (
              <p className="text-xs text-foreground/60">
                {selectedGroup.ready_for_evaluation
                  ? t("submissions.groupReady")
                  : t("submissions.groupNotReady", {
                      total: selectedGroup.weights_total ?? 0,
                      gradeScale: selectedGroup.grade_scale,
                      criteriaCount: selectedGroup.criteria?.length ?? 0,
                    })}
              </p>
            ) : null}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">
              {t("submissions.files")}
            </label>
            <div
              className="relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-muted-foreground/25 bg-muted/20 px-6 py-10 transition-colors hover:bg-muted/40 cursor-pointer"
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                  handleFilesSelected(e.dataTransfer.files);
                }
              }}
              onClick={() =>
                document.getElementById("file-upload-input")?.click()
              }
            >
              <input
                id="file-upload-input"
                key={fileInputKey}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.txt,.zip"
                multiple
                onChange={(event) => handleFilesSelected(event.target.files)}
              />
              <div className="flex flex-col items-center justify-center text-center">
                <div className="mb-4 rounded-full bg-primary/10 p-4 shrink-0 transition-transform duration-300 hover:scale-110">
                  <UploadCloud className="h-6 w-6 text-primary" />
                </div>
                <p className="mb-1 font-medium">
                  {t("submissions.dragAndDrop", "اسحب وأفلت الملفات هنا")}
                </p>
                <p className="text-sm text-foreground/60">
                  {t("submissions.browseFiles", "أو انقر لتصفح ملفاتك")}
                </p>
              </div>
            </div>
          </div>
          <p className="text-xs text-foreground/60">
            {t("submissions.studentIdExtractionHint")}
          </p>
          <p className="text-xs text-foreground/60">
            {t("submissions.archiveUploadHint")}
          </p>
          {files.length ? (
            <div className="rounded-2xl bg-muted/70 p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-semibold">
                  {t("submissions.preUploadCheckTitle")}
                </h3>
                {previewMutation.isPending ? (
                  <Badge>{t("common.loading")}</Badge>
                ) : (
                  <Badge>{previewRows.length}</Badge>
                )}
              </div>
              {duplicatePreviewRows.length ? (
                <div className="mb-4 rounded-2xl border border-destructive/40 bg-destructive/5 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <h4 className="font-semibold text-destructive">
                      {t("submissions.duplicateFilesDetectedTitle")}
                    </h4>
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-10 self-start text-red-700 hover:bg-red-100 dark:text-red-300 dark:hover:bg-red-900/40"
                      onClick={handleRemoveAllDuplicatePreviewFiles}
                    >
                      <span className="inline-flex items-center gap-2">
                        <Trash2 size={16} />
                        {t("submissions.removeAllDuplicateFiles")}
                      </span>
                    </Button>
                  </div>
                  <p className="mt-1 text-sm text-foreground/70">
                    {t("submissions.duplicateFilesDetectedHint")}
                  </p>
                  <div className="mt-3 space-y-3">
                    {duplicatePreviewRows.map((row) => (
                      <div
                        key={`duplicate:${row.localKey}`}
                        className="rounded-2xl border border-destructive/50 bg-destructive/10 p-3"
                      >
                        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                          <div className="space-y-1">
                            <p className="font-medium">
                              {row.original_filename}
                            </p>
                            <p className="text-xs text-foreground/60">
                              {t("common.studentId")}:{" "}
                              {row.student_id || t("common.notAvailable")}
                            </p>
                            <div className="space-y-1 text-xs text-destructive">
                              {getDistinctFriendlyReasons(
                                row.duplicate_reasons,
                              ).map((reason) => (
                                <p key={`${row.localKey}:${reason}`}>
                                  {reason}
                                </p>
                              ))}
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            type="button"
                            onClick={() =>
                              handleRemovePreviewFile(row.localKey)
                            }
                          >
                            <span className="inline-flex items-center gap-2">
                              <Trash2 size={16} />
                              {t("submissions.removeFromUpload")}
                            </span>
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {existingDuplicatePreviewRows.length ? (
                <div className="mb-4 rounded-2xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <h4 className="font-semibold text-amber-700 dark:text-amber-300">
                      {t("submissions.existingDuplicatesDetectedTitle")}
                    </h4>
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-10 self-start text-red-700 hover:bg-red-100 dark:text-red-300 dark:hover:bg-red-900/40"
                      onClick={handleRemoveAllDuplicatePreviewFiles}
                    >
                      <span className="inline-flex items-center gap-2">
                        <Trash2 size={16} />
                        {t("submissions.removeAllDuplicateFiles")}
                      </span>
                    </Button>
                  </div>
                  <p className="mt-1 text-sm text-amber-700/90 dark:text-amber-300/90">
                    {t("submissions.existingDuplicatesDetectedHint")}
                  </p>
                </div>
              ) : null}
              {unsupportedPreviewRows.length ? (
                <div className="mb-4 rounded-2xl border border-red-300 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950/30">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <h4 className="font-semibold text-red-700 dark:text-red-300">
                      {t("submissions.unsupportedFilesDetectedTitle")}
                    </h4>
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-10 self-start text-red-700 hover:bg-red-100 dark:text-red-300 dark:hover:bg-red-900/40"
                      onClick={handleRemoveAllUnsupportedPreviewFiles}
                    >
                      <span className="inline-flex items-center gap-2">
                        <Trash2 size={16} />
                        {t("submissions.removeAllUnsupportedFiles")}
                      </span>
                    </Button>
                  </div>
                  <p className="mt-1 text-sm text-red-700/90 dark:text-red-300/90">
                    {t("submissions.unsupportedFilesDetectedHint")}
                  </p>
                </div>
              ) : null}
              {previewRows.length ? (
                <div className="space-y-3">
                  {previewRows.map((row) => (
                    <div
                      key={row.localKey}
                      className={
                        row.is_duplicate ||
                        !row.accepted ||
                        row.has_existing_match
                          ? "rounded-2xl border border-red-300 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950/30"
                          : "rounded-2xl border border-border/60 bg-background/70 p-3"
                      }
                    >
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div className="space-y-1">
                          <p className="font-medium">{row.original_filename}</p>
                          {row.duplicate_reasons.length ||
                          row.has_existing_match ? null : (
                            <p
                              className={
                                row.accepted
                                  ? "text-xs text-foreground/60"
                                  : "text-xs text-red-700 dark:text-red-300"
                              }
                            >
                              {row.reason
                                ? getUserFacingReason(row.reason)
                                : t("submissions.studentIdDetected")}
                            </p>
                          )}
                          {row.duplicate_reasons.length ? (
                            <div className="space-y-1 text-xs text-destructive">
                              {getDistinctFriendlyReasons(
                                row.duplicate_reasons,
                              ).map((reason) => (
                                <p key={`${row.localKey}:${reason}`}>
                                  {reason}
                                </p>
                              ))}
                            </div>
                          ) : null}
                          {row.has_existing_match ? (
                            <div className="space-y-1 text-xs text-amber-700 dark:text-amber-300">
                              <p>
                                {row.existing_submission_evaluated
                                  ? t(
                                      "submissions.alreadyEvaluatedExistingSubmission",
                                    )
                                  : t(
                                      "submissions.alreadyUploadedExistingSubmission",
                                    )}
                              </p>
                            </div>
                          ) : null}
                        </div>
                        <div className="flex w-full flex-col gap-3 md:w-auto md:flex-row md:items-center">
                          {row.needs_student_id ? (
                            <div className="w-full md:w-56">
                              <Input
                                value={studentIdDrafts[row.localKey] ?? ""}
                                onChange={(event) =>
                                  setStudentIdDrafts((current) => ({
                                    ...current,
                                    [row.localKey]: normalizeStudentIdInput(
                                      event.target.value,
                                    ),
                                  }))
                                }
                                inputMode="numeric"
                                pattern="\d{5,}"
                                placeholder={t(
                                  "submissions.manualStudentIdPlaceholder",
                                )}
                              />
                            </div>
                          ) : (
                            <Badge>{row.student_id}</Badge>
                          )}
                          <Button
                            variant="ghost"
                            type="button"
                            onClick={() =>
                              handleRemovePreviewFile(row.localKey)
                            }
                          >
                            <span className="inline-flex items-center gap-2">
                              <Trash2 size={16} />
                              {t("submissions.removeFromUpload")}
                            </span>
                          </Button>
                          {row.has_existing_match ? (
                            <Button
                              variant={
                                approvedExistingDuplicateKeys.includes(
                                  row.localKey,
                                )
                                  ? "secondary"
                                  : "primary"
                              }
                              type="button"
                              onClick={() =>
                                setApprovedExistingDuplicateKeys((current) =>
                                  current.includes(row.localKey)
                                    ? current.filter(
                                        (key) => key !== row.localKey,
                                      )
                                    : [...current, row.localKey],
                                )
                              }
                            >
                              {approvedExistingDuplicateKeys.includes(
                                row.localKey,
                              )
                                ? t(
                                    "submissions.cancelContinueExistingDuplicate",
                                  )
                                : t("submissions.continueExistingDuplicate")}
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-foreground/70">
                  {t("submissions.preUploadCheckEmpty")}
                </p>
              )}
            </div>
          ) : null}
          <label className="flex items-center gap-3 text-sm">
            <input
              checked={evaluateAfterUpload}
              onChange={(event) => setEvaluateAfterUpload(event.target.checked)}
              type="checkbox"
              className="size-4"
            />
            {t("submissions.autoEvaluate")}
          </label>
          <Button
            className="w-full"
            onClick={submitUpload}
            type="button"
            disabled={
              uploadMutation.isPending ||
              previewMutation.isPending ||
              duplicatePreviewRows.length > 0 ||
              unresolvedExistingDuplicateRows.length > 0 ||
              unsupportedPreviewRows.length > 0
            }
          >
            {uploadMutation.isPending
              ? t("common.loading")
              : t("submissions.upload")}
          </Button>
        </Card>

        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold">{t("submissions.title")}</h3>
            <div className="flex items-center gap-2">
              <Badge>{groupId ? submissionsTotal : 0}</Badge>
              <Button
                variant={isBatchActive ? "secondary" : "primary"}
                type="button"
                onClick={handleEvaluateAllClick}
                disabled={
                  isBatchActive
                    ? cancelBatchMutation.isPending ||
                      Boolean(batchStatus?.cancel_requested)
                    : !groupId ||
                      !evaluatableSubmissionIds.length ||
                      isEvaluateAllBusy ||
                      evaluatableSubmissionIdsQuery.isFetching
                }
              >
                {evaluateAllButtonLabel}
              </Button>
            </div>
          </div>
          {batchStatus?.active ? (
            <div className="mb-4 rounded-2xl border border-blue-300 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950/30">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <p className="font-semibold text-blue-700 dark:text-blue-300">
                    {t("submissions.batchTrackingTitle")}
                  </p>
                  <p className="text-sm text-blue-700/90 dark:text-blue-300/90">
                    {t("submissions.batchTrackingProgress", {
                      processed: batchStatus.processed_count,
                      total: batchStatus.total_count,
                      percent: batchProgressPercent,
                      completed: batchStatus.completed_count,
                      failed: batchStatus.failed_count,
                    })}
                  </p>
                  {batchStatus.current_submission_id ? (
                    <p className="text-xs text-blue-700/90 dark:text-blue-300/90">
                      {t("submissions.batchCurrentFile", {
                        filename:
                          currentBatchSubmission?.original_filename ||
                          batchStatus.current_submission_id,
                      })}
                    </p>
                  ) : null}
                  {batchStatus.cancel_requested ? (
                    <p className="text-xs font-medium text-amber-700 dark:text-amber-300">
                      {t("submissions.batchCancelPending")}
                    </p>
                  ) : null}
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={handleEvaluateAllClick}
                  disabled={
                    cancelBatchMutation.isPending ||
                    batchStatus.cancel_requested
                  }
                >
                  {batchStatus.cancel_requested
                    ? t("submissions.batchCancelPending")
                    : cancelBatchMutation.isPending
                      ? t("common.loading")
                      : t("submissions.stopBatch")}
                </Button>
              </div>
            </div>
          ) : null}
          {!groupId ? (
            <EmptyState
              title={t("submissions.filteredViewTitle")}
              description={t("submissions.selectGroupToView")}
            />
          ) : submissionRows.length ? (
            <div className="space-y-3">
              {submissionRows.map((submission) => {
                const actionState = getSubmissionActionState(submission);
                return (
                  <div
                    key={submission.id}
                    className="rounded-2xl bg-muted/70 p-4"
                  >
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="space-y-2">
                        <p className="font-semibold">
                          {submission.original_filename}
                        </p>
                        <p className="text-sm text-foreground/70">
                          {submission.student_id?.trim() ||
                            t("common.notAvailable")}
                        </p>
                        <Badge
                          className={getStatusBadgeColor(submission.status)}
                        >
                          {t(`state.${submission.status}`)}
                        </Badge>
                        {submission.status === "failed" ? (
                          <p className="text-xs text-destructive">
                            {t("submissions.failureReasonLabel")}:{" "}
                            {getUserFacingReason(
                              submission.error_message,
                              "errors.evaluation.failed",
                            )}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {actionState &&
                        canEvaluateSubmission(
                          submission.status,
                          submission.student_id,
                        ) ? (
                          <Button
                            variant={actionState.variant}
                            type="button"
                            onClick={() =>
                              evaluateMutation.mutate(submission.id)
                            }
                            disabled={
                              actionState.disabled ||
                              startBatchMutation.isPending
                            }
                          >
                            {actionState.label}
                          </Button>
                        ) : null}
                        <Link to={`/submissions/${submission.id}/evaluations`}>
                          <Button variant="secondary">
                            {t("submissions.viewEvaluations")}
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </div>
                );
              })}
              <PaginationControls
                page={submissionsPage}
                pageSize={submissionsPageSize}
                total={submissionsTotal}
                isFetching={submissionsQuery.isFetching}
                onPageChange={setSubmissionsPage}
                onPageSizeChange={(pageSize) => {
                  setSubmissionsPageSize(pageSize);
                  setSubmissionsPage(1);
                }}
              />
            </div>
          ) : (
            <EmptyState
              title={t("submissions.title")}
              description={t("submissions.empty")}
            />
          )}
        </Card>
      </div>
      {groupId ? (
        <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <h3 className="text-lg font-semibold">
                {t("submissions.reportTableTitle")}
              </h3>
              <p className="text-sm text-foreground/70">
                {t("submissions.reportTableHint")}
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Input
                value={reportSearch}
                onChange={(event) => setReportSearch(event.target.value)}
                placeholder={t("submissions.reportSearch")}
                className="sm:w-72"
              />
              <Button type="button" onClick={exportReportToExcel}>
                {t("submissions.exportExcel")}
              </Button>
            </div>
          </div>
          {reportCriterionNames.length ? (
            <div className="mb-4 flex flex-wrap gap-2">
              {reportCriterionNames.map((criterionName) => (
                <button
                  key={criterionName}
                  type="button"
                  onClick={() => setActiveCriterionTab(criterionName)}
                  className={
                    activeCriterionTab === criterionName
                      ? "rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white"
                      : "rounded-full border border-border/60 bg-background px-4 py-2 text-sm font-semibold text-foreground/70"
                  }
                >
                  {criterionName}
                </button>
              ))}
            </div>
          ) : null}
          {reportRows.length ? (
            <>
              <div className="overflow-x-auto rounded-xl border border-border/50 shadow-sm">
                <table className="w-full text-sm">
                  <thead className="bg-primary/10">
                    <tr className="border-b border-primary/20 text-primary text-right">
                      <th className="px-4 py-4 font-bold whitespace-nowrap text-start">
                        {t("common.filename")}
                      </th>
                      <th className="px-4 py-4 font-bold whitespace-nowrap text-center">
                        {t("common.studentId")}
                      </th>
                      <th className="px-4 py-4 font-bold whitespace-nowrap text-center">
                        {t("common.status")}
                      </th>
                      <th className="px-4 py-4 font-bold whitespace-nowrap text-center">
                        {t("submissions.totalAiScoreColumn")}
                      </th>
                      <th className="px-4 py-4 font-bold whitespace-nowrap text-center">
                        {t("submissions.finalAdjustedScoreColumn")}
                      </th>
                      <th className="px-4 py-4 font-bold whitespace-nowrap text-center">
                        {activeCriterionTab ||
                          t("submissions.criteriaResultsColumn")}
                      </th>
                      <th className="px-4 py-4 font-bold whitespace-nowrap text-center">
                        {t("common.actions")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {reportRows.map((row) => (
                      <tr
                        key={row.submission.id}
                        className="align-middle transition-colors hover:bg-muted/20"
                      >
                        <td className="px-4 py-4 font-medium text-foreground/90 w-[200px]">
                          <span
                            className="line-clamp-2"
                            title={row.submission.original_filename}
                          >
                            {row.submission.original_filename}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-center">
                          <span className="inline-block rounded-md bg-muted/50 px-2 py-1 text-xs font-medium">
                            {row.submission.student_id ||
                              t("common.notAvailable")}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-center">
                          <div className="flex flex-col items-center justify-center gap-1">
                            <Badge
                              className={`whitespace-nowrap ${getStatusBadgeColor(row.submission.status)}`}
                            >
                              {t(`state.${row.submission.status}`)}
                            </Badge>
                            {row.submission.status === "failed" ? (
                              <p className="mt-1 max-w-[150px] text-[10px] text-destructive leading-tight">
                                {getUserFacingReason(
                                  row.submission.error_message,
                                  "errors.evaluation.failed",
                                )}
                              </p>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-4 py-4 text-center font-semibold">
                          {row.latest_evaluation?.total_ai_score != null
                            ? row.latest_evaluation.total_ai_score.toFixed(2)
                            : "-"}
                        </td>
                        <td className="px-4 py-4 text-center font-semibold text-primary">
                          {row.latest_evaluation?.final_adjusted_score != null
                            ? row.latest_evaluation.final_adjusted_score.toFixed(
                                2,
                              )
                            : "-"}
                        </td>
                        <td className="px-4 py-4 text-center">
                          {renderCriterionResultForRow(row)}
                        </td>
                        <td className="px-4 py-4 text-center">
                          {row.latest_evaluation ? (
                            <Link
                              to={`/evaluations/${row.latest_evaluation.id}#manual-adjustments`}
                            >
                              <Button
                                variant="secondary"
                                className="h-8 px-3 text-xs whitespace-nowrap shadow-sm hover:shadow-md"
                              >
                                {t("submissions.manualAdjust", "تعديل يدوي")}
                              </Button>
                            </Link>
                          ) : (
                            <span className="text-xs text-foreground/50">
                              {t("common.notAvailable")}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <PaginationControls
                page={reportPage}
                pageSize={reportPageSize}
                total={reportTotal}
                isFetching={reportQuery.isFetching}
                onPageChange={setReportPage}
                onPageSizeChange={(pageSize) => {
                  setReportPageSize(pageSize);
                  setReportPage(1);
                }}
              />
            </>
          ) : (
            <EmptyState
              title={t("submissions.reportTableTitle")}
              description={t("empty.noData")}
            />
          )}
        </Card>
      ) : null}
      {missingStudentTotal ? (
        <Card className="p-5">
          <div className="mb-4 space-y-1">
            <h3 className="text-lg font-semibold">
              {t("submissions.missingStudentIdsTitle")}
            </h3>
            <p className="text-sm text-foreground/70">
              {t("submissions.missingStudentIdsHint")}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 text-right">
                  <th className="px-3 py-2 font-medium">
                    {t("common.filename")}
                  </th>
                  <th className="px-3 py-2 font-medium">
                    {t("common.status")}
                  </th>
                  <th className="px-3 py-2 font-medium">
                    {t("common.studentId")}
                  </th>
                  <th className="px-3 py-2 font-medium">
                    {t("common.actions")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {missingStudentIdSubmissions.map((submission) => (
                  <tr
                    key={submission.id}
                    className="border-b border-border/40 last:border-0"
                  >
                    <td className="px-3 py-3">
                      {submission.original_filename}
                    </td>
                    <td className="px-3 py-3">
                      <Badge>{t(`state.${submission.status}`)}</Badge>
                    </td>
                    <td className="px-3 py-3">
                      <Input
                        value={studentIdDrafts[submission.id] ?? ""}
                        onChange={(event) =>
                          setStudentIdDrafts((current) => ({
                            ...current,
                            [submission.id]: normalizeStudentIdInput(
                              event.target.value,
                            ),
                          }))
                        }
                        inputMode="numeric"
                        pattern="\d{5,}"
                        placeholder={t(
                          "submissions.manualStudentIdPlaceholder",
                        )}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <Button
                        type="button"
                        onClick={() => handleSaveStudentId(submission.id)}
                        disabled={
                          saveStudentIdMutation.isPending &&
                          saveStudentIdMutation.variables?.submissionId ===
                            submission.id
                        }
                      >
                        {saveStudentIdMutation.isPending &&
                        saveStudentIdMutation.variables?.submissionId ===
                          submission.id
                          ? t("common.loading")
                          : t("submissions.saveStudentId")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationControls
            page={missingStudentPage}
            pageSize={missingStudentPageSize}
            total={missingStudentTotal}
            isFetching={missingStudentQuery.isFetching}
            onPageChange={setMissingStudentPage}
            onPageSizeChange={(pageSize) => {
              setMissingStudentPageSize(pageSize);
              setMissingStudentPage(1);
            }}
          />
        </Card>
      ) : null}
    </div>
  );
}
