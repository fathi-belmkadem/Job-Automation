{{/* Common labels for a given app name (xing | join | latex-compiler) */}}
{{- define "job-automation.labels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/part-of: job-automation
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "job-automation.image" -}}
{{ .root.Values.imageRegistry }}/{{ .repository }}:{{ .root.Values.imageTag }}
{{- end -}}
