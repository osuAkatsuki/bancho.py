{{/*
Expand the name of the chart.
*/}}
{{- define "banchopy.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "banchopy.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "banchopy.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "banchopy.labels" -}}
helm.sh/chart: {{ include "banchopy.chart" . }}
{{ include "banchopy.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "banchopy.selectorLabels" -}}
app.kubernetes.io/name: {{ include "banchopy.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "banchopy.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "banchopy.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "banchopy.baseConfig" -}}
# for nginx reverse proxy to work through the containers, the bancho
# server must expose itself on port 80 to be accessed on http://bancho.
SERVER_ADDR: "0.0.0.0"
SERVER_PORT: !!str 80

# Chimu: https://api.chimu.moe/cheesegull/search - https://api.chimu.moe/v1/download
# osu.direct: https://osu.direct/api/search - https://osu.direct/d
MIRROR_SEARCH_ENDPOINT: https://catboy.best/api/search
MIRROR_DOWNLOAD_ENDPOINT: https://catboy.best/d

# XXX: change your domain if applicable
DOMAIN: {{ .Values.global.domain }}

COMMAND_PREFIX: !

SEASONAL_BGS: https://akatsuki.pw/static/flower.png,https://i.cmyui.xyz/nrMT4V2RR3PR.jpeg

MENU_ICON_URL: https://akatsuki.pw/static/logos/logo_ingame.png
MENU_ONCLICK_URL: https://akatsuki.pw

DEBUG: 'False'

# redirect beatmaps, beatmapsets, and forum
# pages of maps to the official osu! website
REDIRECT_OSU_URLS: 'True'

PP_CACHED_ACCS: 90,95,98,99,100

DISALLOWED_NAMES: mrekk,vaxei,btmc,cookiezi
DISALLOWED_PASSWORDS: password,abc123
DISALLOW_OLD_CLIENTS: 'True'

DISCORD_AUDIT_LOG_WEBHOOK: ''

# automatically share information with the primary
# developer of bancho.py (https://github.com/cmyui)
# for debugging & development purposes.
AUTOMATICALLY_REPORT_PROBLEMS: 'False'

# advanced dev settings

## WARNING: only touch this once you've
##          read through what it enables.
##          you could put your server at risk.
DEVELOPER_MODE: 'False'
{{- end }}

{{- define "banchopy.basePvcConfig" -}}
{{- if .args.enabled -}}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ printf "%s-%s" (include "banchopy.fullname" .global) .suffix }}
  labels:
    {{- toYaml .args.labels | nindent 4 }}
  annotations:
    {{- toYaml .args.annotations | nindent 4 }}
spec:
  storageClassName: {{ .args.storageClass }}
  resources:
    requests:
      storage: {{ .args.size }}
  accessModes: {{ .args.accessModes }}
---
{{- end -}}
{{- end }}
