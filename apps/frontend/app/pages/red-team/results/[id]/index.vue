<template>
  <v-container fluid class="results-page">
    <!-- Loading state -->
    <div v-if="loading" class="d-flex justify-center align-center" style="min-height: 300px;">
      <v-progress-circular indeterminate color="primary" />
    </div>

    <template v-else-if="run">
      <!-- Header -->
      <div class="mb-6">
        <div class="d-flex align-center mb-1">
          <v-btn
            icon="mdi-arrow-left"
            variant="text"
            size="small"
            class="mr-2"
            :to="'/red-team'"
          />
          <h1 class="text-h5">{{ pageTitle }}</h1>
          <v-chip
            v-if="isDemoTarget"
            color="purple"
            variant="tonal"
            size="small"
            prepend-icon="mdi-robot"
            class="ml-3"
            label
          >
            Demo
          </v-chip>
        </div>
        <p class="text-body-2 text-medium-emphasis" data-testid="header-info">
          <v-icon :icon="targetIcon" size="x-small" class="mr-1" />
          {{ targetLabel }}
          &nbsp;·&nbsp; {{ humanPack(run.pack) }}
          &nbsp;·&nbsp;
          <v-tooltip location="bottom">
            <template #activator="{ props: tip }">
              <span v-bind="tip" style="cursor: help; text-decoration: underline dotted;">{{ timeAgo }}</span>
            </template>
            <div class="text-caption">
              <div>Started: {{ formatTimestamp(run.created_at) }}</div>
              <div v-if="run.completed_at">Finished: {{ formatTimestamp(run.completed_at) }}</div>
              <div v-if="run.created_at && run.completed_at">Duration: {{ durationLabel }}</div>
            </div>
          </v-tooltip>
          <v-chip
            v-if="runClass"
            :color="runClass.color"
            variant="tonal"
            size="x-small"
            :prepend-icon="runClass.icon"
            class="ml-2"
            data-testid="run-type-chip"
          >
            {{ runClass.type === 'protected' ? 'Protected' : 'Baseline' }}
          </v-chip>
        </p>
        <div v-if="targetEndpointUrl" class="mt-1 d-flex align-center text-body-2" style="font-family: monospace; color: #1565c0;">
          <v-icon size="16" class="mr-1" color="blue-darken-2">mdi-link-variant</v-icon>
          {{ targetEndpointUrl }}
        </div>
      </div>

      <!-- Safe mode banner -->
      <v-alert
        v-if="skippedMutating > 0"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="safe-mode-banner"
      >
        <template #text>
          Safe mode was enabled — {{ skippedMutating }} mutating scenario{{ skippedMutating !== 1 ? 's were' : ' was' }} skipped.
        </template>
      </v-alert>

      <!-- All-skipped banner -->
      <v-alert
        v-if="run.executed === 0 && run.total_applicable === 0"
        type="warning"
        variant="tonal"
        class="mb-4"
        data-testid="all-skipped-banner"
      >
        No scenarios were applicable. Try disabling Safe mode or selecting a different pack.
      </v-alert>

      <!-- Few-executed warning -->
      <v-alert
        v-else-if="run.executed > 0 && run.executed < 5"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="few-executed-warning"
      >
        Score based on only {{ run.executed }} scenario{{ run.executed !== 1 ? 's' : '' }}. May not be fully representative.
      </v-alert>

      <!-- Partial results -->
      <v-alert
        v-else-if="run.status === 'cancelled' || (run.status === 'failed' && run.executed > 0)"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="partial-results-banner"
      >
        Partial results &mdash; {{ run.executed }} of {{ run.total_applicable }} scenarios completed.
      </v-alert>

      <!-- ================================================================ -->
      <!-- PROTECTED RUN: Before → After hero                                -->
      <!-- ================================================================ -->
      <template v-if="!isBaseline && run.executed > 0">
        <!-- Before / After comparison hero -->
        <v-card
          v-if="comparison"
          variant="flat"
          class="mb-6 pa-5"
          data-testid="before-after-hero"
        >
          <div class="text-center mb-4">
            <h2 class="text-h6 font-weight-bold mb-1">Before → After</h2>
            <p class="text-body-2 text-medium-emphasis">Same attacks, with AI Protector enabled</p>
          </div>

          <v-row align="center" justify="center" class="text-center">
            <!-- Before -->
            <v-col cols="5">
              <div class="text-caption text-medium-emphasis text-uppercase mb-1">Without protection</div>
              <div class="text-h4 font-weight-bold" style="color: #78909c;">
                {{ comparison.run_a.score_simple ?? 0 }}<span class="text-h6 text-medium-emphasis">/100</span>
              </div>
              <div class="text-caption text-medium-emphasis">
                {{ baselineFailedCount }} attack{{ baselineFailedCount !== 1 ? 's' : '' }} got through
              </div>
            </v-col>

            <!-- Arrow + delta -->
            <v-col cols="2" class="d-flex flex-column align-center">
              <v-icon icon="mdi-arrow-right" size="large" color="primary" />
              <v-chip
                :color="comparison.score_delta >= 0 ? 'success' : 'error'"
                variant="tonal"
                size="small"
                class="mt-1"
              >
                {{ comparison.score_delta >= 0 ? '+' : '' }}{{ comparison.score_delta }}
              </v-chip>
            </v-col>

            <!-- After -->
            <v-col cols="5">
              <div class="text-caption text-medium-emphasis text-uppercase mb-1">With AI Protector</div>
              <div class="text-h4 font-weight-bold" :style="{ color: scoreMeta.color }">
                {{ comparison.run_b.score_simple ?? 0 }}<span class="text-h6 text-medium-emphasis">/100</span>
              </div>
              <div class="text-caption text-medium-emphasis">
                {{ failedCount }} attack{{ failedCount !== 1 ? 's' : '' }} got through
              </div>
            </v-col>
          </v-row>

          <div class="text-center mt-4">
            <v-chip color="success" variant="tonal" size="small" class="mr-2">
              {{ comparison.fixed_failures.length }} vulnerabilities fixed
            </v-chip>
            <v-chip v-if="comparison.new_failures.length > 0" color="warning" variant="tonal" size="small">
              {{ comparison.new_failures.length }} new
            </v-chip>
          </div>
        </v-card>

        <!-- Protected score hero (no comparison available) -->
        <v-card v-else variant="flat" class="mb-6 pa-5" data-testid="score-section">
          <v-row align="center">
            <v-col cols="12" md="5" class="d-flex flex-column align-center align-md-start text-center text-md-start">
              <div class="d-flex align-center ga-4 mb-3">
                <div class="score-badge" :style="{ borderColor: scoreMeta.color }">
                  <span class="score-value" :style="{ color: scoreMeta.color }">{{ run.score_simple ?? 0 }}</span>
                </div>
                <div>
                  <v-chip :color="scoreMeta.vuetifyColor" variant="tonal" size="small" class="mb-1" data-testid="score-label">
                    {{ scoreMeta.label }}
                  </v-chip>
                  <p class="text-caption text-medium-emphasis mb-0">{{ run.executed }} attacks tested</p>
                </div>
              </div>
            </v-col>
            <v-col cols="12" md="7">
              <div class="d-flex flex-wrap ga-4 mb-4">
                <div class="text-center">
                  <span class="text-h6 font-weight-bold text-success">{{ run.passed }}</span>
                  <p class="text-caption text-medium-emphasis mb-0">blocked</p>
                </div>
                <div class="text-center">
                  <span class="text-h6 font-weight-bold text-error">{{ failedCount }}</span>
                  <p class="text-caption text-medium-emphasis mb-0">got through</p>
                </div>
                <div v-if="criticalCount > 0" class="text-center">
                  <span class="text-h6 font-weight-bold" style="color: #d32f2f;">{{ criticalCount }}</span>
                  <p class="text-caption text-medium-emphasis mb-0">high/critical</p>
                </div>
              </div>

              <div class="d-flex flex-wrap ga-2">
                <v-btn variant="outlined" size="small" prepend-icon="mdi-replay" :loading="isRerunning" @click="onRerun">
                  Re-run
                </v-btn>
                <v-btn variant="text" size="small" prepend-icon="mdi-file-pdf-box" :loading="isExporting" @click="onExport">
                  Export PDF
                </v-btn>
              </div>
            </v-col>
          </v-row>
        </v-card>

        <!-- Adoption bridge — what's next after protected run -->
        <v-card v-if="failedCount === 0" variant="flat" class="mb-6 pa-4" style="border-left: 4px solid rgb(var(--v-theme-success));">
          <div class="d-flex align-center mb-2">
            <v-icon icon="mdi-shield-check" color="success" class="mr-2" />
            <span class="text-subtitle-2 font-weight-bold">All tested attacks were blocked in this run</span>
          </div>
          <p class="text-body-2 text-medium-emphasis mb-3">
            Deploy AI Protector in front of your production endpoint to get the same protection at runtime.
          </p>
          <div class="d-flex flex-wrap ga-2">
            <v-btn variant="outlined" size="small" prepend-icon="mdi-file-pdf-box" :loading="isExporting" @click="onExport">
              Export PDF report
            </v-btn>
            <v-btn variant="text" size="small" prepend-icon="mdi-replay" :loading="isRerunning" @click="onRerun">
              Re-run scan
            </v-btn>
          </div>
        </v-card>

        <!-- Strengthen protection further — when some attacks still got through -->
        <v-card v-else-if="failedCount > 0" variant="flat" class="mb-6 pa-4" style="border-left: 4px solid rgb(var(--v-theme-warning));">
          <div class="d-flex align-center mb-2">
            <v-icon icon="mdi-shield-alert" color="warning" class="mr-2" />
            <span class="text-subtitle-2 font-weight-bold">Strengthen protection further</span>
          </div>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ failedCount }} attack{{ failedCount !== 1 ? 's' : '' }} still got through with the current policy. Try a stricter profile or add custom rules to close the remaining gaps.
          </p>
          <div class="d-flex flex-wrap ga-2">
            <v-btn variant="outlined" size="small" prepend-icon="mdi-replay" :loading="isRerunning" @click="onRerun">
              Re-run with stricter policy
            </v-btn>
            <v-btn variant="text" size="small" prepend-icon="mdi-file-pdf-box" :loading="isExporting" @click="onExport">
              Export PDF
            </v-btn>
          </div>
        </v-card>
      </template>

      <!-- ================================================================ -->
      <!-- BASELINE RUN: Issue-led hero                                      -->
      <!-- ================================================================ -->
      <template v-if="isBaseline && run.executed > 0">
        <!-- Issue-led hero — failed attacks as the big number -->
        <v-card variant="flat" class="mb-6 pa-5" data-testid="score-section">
          <v-row align="center">
            <!-- LEFT: Failed count as hero -->
            <v-col cols="12" md="5" class="d-flex flex-column align-center align-md-start text-center text-md-start">
              <div class="d-flex align-center ga-4 mb-3">
                <div class="score-badge" style="border-color: #d32f2f;">
                  <span class="score-value" style="color: #d32f2f;">{{ failedCount }}</span>
                </div>
                <div>
                  <span class="text-subtitle-1 font-weight-bold">
                    {{ failedCount === 0 ? 'No attacks got through' : `attack${failedCount !== 1 ? 's' : ''} got through` }}
                  </span>
                  <p class="text-caption text-medium-emphasis mb-0">
                    out of {{ run.executed }} tested · no protection active
                  </p>
                </div>
              </div>
              <p v-if="failedCount > 0" class="text-body-2 text-medium-emphasis mb-0" data-testid="score-interpretation">
                These attacks got through without any firewall in place. Enable AI Protector and re-run to see how many get blocked.
              </p>
              <p v-else class="text-body-2 text-medium-emphasis mb-0" data-testid="score-interpretation">
                The model resisted all attacks on its own — but model behavior changes over time. Enable AI Protector for enforced protection.
              </p>
            </v-col>

            <!-- RIGHT: Stats + CTA -->
            <v-col cols="12" md="7">
              <div class="d-flex flex-wrap ga-4 mb-4">
                <div class="text-center">
                  <span class="text-h6 font-weight-bold text-error">{{ failedCount }}</span>
                  <p class="text-caption text-medium-emphasis mb-0">got through</p>
                </div>
                <v-tooltip location="top">
                  <template #activator="{ props }">
                    <div v-bind="props" class="text-center" style="cursor: help;">
                      <span class="text-h6 font-weight-bold text-success">{{ run.passed }}</span>
                      <p class="text-caption text-medium-emphasis mb-0">not exploited in this run</p>
                    </div>
                  </template>
                  <span>These attacks were sent but not exploited — model behavior may vary between runs.</span>
                </v-tooltip>
                <div v-if="criticalCount > 0" class="text-center">
                  <span class="text-h6 font-weight-bold" style="color: #d32f2f;">{{ criticalCount }}</span>
                  <p class="text-caption text-medium-emphasis mb-0">high/critical</p>
                </div>
                <div v-if="run.skipped > 0" class="text-center">
                  <span class="text-h6 font-weight-bold text-medium-emphasis">{{ run.skipped }}</span>
                  <p class="text-caption text-medium-emphasis mb-0">skipped</p>
                </div>
              </div>

              <!-- Protection not active banner — inline -->
              <v-alert
                color="warning"
                variant="tonal"
                density="compact"
                class="mb-4"
                data-testid="baseline-banner"
              >
                <template #prepend>
                  <v-icon icon="mdi-shield-off-outline" />
                </template>
                <template #text>
                  <strong>No enforced protection.</strong> Safe outcomes came from model behavior alone — they may not hold across providers, prompt changes, or model updates.
                </template>
              </v-alert>

              <!-- Recommended next step -->
              <div class="mb-2">
                <span class="text-caption text-uppercase font-weight-bold text-medium-emphasis">Recommended next step</span>
              </div>
              <div class="d-flex flex-wrap ga-2 mb-1">
                <v-btn
                  v-if="isDemoTarget"
                  color="primary"
                  variant="flat"
                  size="default"
                  prepend-icon="mdi-shield-check"
                  :loading="isRerunning"
                  data-testid="hero-protect-rerun-btn"
                  @click="onRerunProtected"
                >
                  Enable protection &amp; re-run
                </v-btn>
                <v-btn
                  v-else
                  color="primary"
                  variant="flat"
                  size="default"
                  prepend-icon="mdi-shield-plus"
                  data-testid="hero-setup-btn"
                  @click="showSetupDialog = true"
                >
                  Set up protection
                </v-btn>
              </div>
              <p v-if="isDemoTarget" class="text-caption text-medium-emphasis mt-2 mb-2">
                One click — AI Protector will filter every attack and re-run the same scan.
              </p>
              <!-- Demoted secondary actions -->
              <div class="d-flex flex-wrap ga-3 mt-2">
                <a class="text-caption text-primary" style="cursor: pointer;" @click="onExport">Export PDF</a>
                <a class="text-caption text-primary" style="cursor: pointer;" :class="{ 'text-disabled': isRerunning }" @click="onRerun">Re-run baseline</a>
              </div>
            </v-col>
          </v-row>
        </v-card>

        <!-- ============================================================== -->
        <!-- What got through — scenario failure cards (ABOVE categories)    -->
        <!-- ============================================================== -->
        <h2 v-if="topFailures.length > 0" class="text-h6 mb-1">What got through</h2>
        <p v-if="topFailures.length > 0" class="text-body-2 text-medium-emphasis mb-3">
          These are the highest-priority failures — each one represents an attack that bypassed the model.
        </p>
        <v-card v-if="topFailures.length > 0" variant="flat" class="mb-6 pa-4" data-testid="what-got-through">
          <v-list density="compact" class="bg-transparent">
            <v-list-item
              v-for="fail in topFailures"
              :key="fail.scenario_id"
              class="px-0 mb-2"
              @click="router.push(`/red-team/results/${runId}/scenario/${fail.scenario_id}`)"
              style="cursor: pointer;"
            >
              <template #prepend>
                <v-icon
                  :icon="severityMeta(fail.severity).icon"
                  :color="severityMeta(fail.severity).color"
                  size="small"
                  class="mr-3"
                />
              </template>
              <v-list-item-title class="text-body-2">
                <span class="font-weight-medium">{{ fail.title || fail.scenario_id }}</span>
              </v-list-item-title>
              <v-list-item-subtitle class="text-caption mt-1">
                {{ humanCategory(fail.category) }}
                <span v-if="failureImpact(fail)" class="text-error">
                  &nbsp;·&nbsp; {{ failureImpact(fail) }}
                </span>
              </v-list-item-subtitle>
              <template #append>
                <div class="d-flex align-center ga-2">
                  <v-chip
                    v-if="failureMitigation(fail)"
                    color="warning"
                    variant="outlined"
                    size="x-small"
                  >
                    {{ failureMitigation(fail) }}
                  </v-chip>
                  <v-chip
                    :color="severityMeta(fail.severity).color"
                    variant="tonal"
                    size="x-small"
                    :prepend-icon="severityMeta(fail.severity).icon"
                  >
                    {{ severityMeta(fail.severity).label }}
                  </v-chip>
                  <v-icon icon="mdi-chevron-right" size="small" />
                </div>
              </template>
            </v-list-item>
          </v-list>
          <div v-if="allFailures.length > 5" class="text-center mt-2">
            <v-btn variant="text" size="small" color="primary" @click="showAllFailures = !showAllFailures">
              {{ showAllFailures ? 'Show less' : `Show all ${allFailures.length} failures` }}
            </v-btn>
          </div>
        </v-card>

        <!-- No failures baseline -->
        <v-card v-else variant="flat" class="mb-6 pa-4" data-testid="what-got-through">
          <div class="text-center pa-4">
            <v-icon icon="mdi-robot-happy" color="blue-grey" size="48" class="mb-2" />
            <p class="text-body-1 font-weight-medium">No attacks got through</p>
            <p class="text-body-2 text-medium-emphasis mb-3">
              The model resisted all attacks on its own. But model behavior changes — enable AI Protector for enforced runtime protection.
            </p>
            <v-btn
              v-if="isDemoTarget"
              color="primary"
              variant="flat"
              size="small"
              prepend-icon="mdi-shield-check"
              :loading="isRerunning"
              @click="onRerunProtected"
            >
              Enable protection &amp; re-run
            </v-btn>
            <v-btn
              v-else
              color="primary"
              variant="flat"
              size="small"
              prepend-icon="mdi-shield-plus"
              @click="showSetupDialog = true"
            >
              Set up protection
            </v-btn>
          </div>
        </v-card>

        <!-- ============================================================== -->
        <!-- What happens after protection — baseline only, two-column card  -->
        <!-- ============================================================== -->
        <v-card variant="flat" class="mb-6 pa-4" data-testid="what-happens-after">
          <h2 class="text-subtitle-1 font-weight-bold mb-3">What happens after protection</h2>
          <v-row>
            <v-col cols="12" sm="6">
              <div class="d-flex align-center mb-2">
                <v-icon icon="mdi-shield-off-outline" color="error" size="small" class="mr-2" />
                <span class="text-subtitle-2 font-weight-medium">Without protection</span>
              </div>
              <ul class="text-body-2 text-medium-emphasis pl-4" style="list-style: disc;">
                <li class="mb-1">Attacks hit the model directly</li>
                <li class="mb-1">Safe outcomes depend on model behavior alone</li>
                <li>Results may vary across model versions</li>
              </ul>
            </v-col>
            <v-col cols="12" sm="6">
              <div class="d-flex align-center mb-2">
                <v-icon icon="mdi-shield-check" color="success" size="small" class="mr-2" />
                <span class="text-subtitle-2 font-weight-medium">With AI Protector</span>
              </div>
              <ul class="text-body-2 text-medium-emphasis pl-4" style="list-style: disc;">
                <li class="mb-1">Every request is inspected before reaching the model</li>
                <li class="mb-1">Known attack patterns are blocked deterministically</li>
                <li>Protection stays consistent across model changes</li>
              </ul>
            </v-col>
          </v-row>
          <div class="text-center mt-4">
            <a
              v-if="isDemoTarget"
              class="text-caption text-primary"
              style="cursor: pointer;"
              @click="onRerunProtected"
            >
              Enable protection &amp; re-run →
            </a>
            <a
              v-else
              class="text-caption text-primary"
              style="cursor: pointer;"
              @click="showSetupDialog = true"
            >
              Set up protection →
            </a>
          </div>
        </v-card>
      </template>

      <!-- ================================================================ -->
      <!-- Category breakdown — shared by baseline and protected              -->
      <!-- ================================================================ -->
      <template v-if="run && run.executed > 0">
        <h2 class="text-h6 mb-3">Category breakdown</h2>
        <v-card variant="flat" class="mb-6 pa-4" data-testid="category-breakdown">
          <div
            v-for="cat in categoryBars"
            :key="cat.slug"
            class="mb-4"
          >
            <div class="d-flex justify-space-between mb-1">
              <span class="text-body-2 font-weight-medium">{{ cat.label }}</span>
              <span class="text-body-2 text-medium-emphasis">
                {{ cat.passedCount }}/{{ cat.total }} {{ isBaseline ? 'not exploited' : 'blocked' }} ({{ cat.percent }}%)
              </span>
            </div>
            <v-progress-linear
              :model-value="cat.percent"
              :color="cat.percent >= 80 ? 'success' : cat.percent >= 60 ? 'warning' : 'error'"
              height="10"
              rounded
            />
            <div v-if="isBaseline" class="d-flex ga-3 mt-1">
              <span class="text-caption text-success">{{ cat.passedCount }} not exploited</span>
              <span class="text-caption text-medium-emphasis">·</span>
              <span class="text-caption text-error">{{ cat.total - cat.passedCount }} got through</span>
            </div>
          </div>
          <p v-if="categoryBars.length === 0" class="text-body-2 text-medium-emphasis">
            No category data available.
          </p>
        </v-card>

        <!-- Top failures for protected runs -->
        <template v-if="!isBaseline && topFailures.length > 0">
          <h2 class="text-h6 mb-3">Remaining vulnerabilities</h2>
          <v-card variant="flat" class="mb-6 pa-4" data-testid="top-failures">
            <v-list density="compact" class="bg-transparent">
              <v-list-item
                v-for="fail in topFailures"
                :key="fail.scenario_id"
                class="px-0 mb-2"
                @click="router.push(`/red-team/results/${runId}/scenario/${fail.scenario_id}`)"
                style="cursor: pointer;"
              >
                <template #prepend>
                  <v-icon
                    :icon="severityMeta(fail.severity).icon"
                    :color="severityMeta(fail.severity).color"
                    size="small"
                    class="mr-3"
                  />
                </template>
                <v-list-item-title class="text-body-2">
                  <span class="font-weight-medium">{{ fail.title || fail.scenario_id }}</span>
                </v-list-item-title>
                <v-list-item-subtitle class="text-caption mt-1">
                  {{ humanCategory(fail.category) }}
                  <span v-if="failureImpact(fail)" class="text-error">
                    &nbsp;·&nbsp; {{ failureImpact(fail) }}
                  </span>
                </v-list-item-subtitle>
                <template #append>
                  <v-chip
                    :color="severityMeta(fail.severity).color"
                    variant="tonal"
                    size="x-small"
                    :prepend-icon="severityMeta(fail.severity).icon"
                  >
                    {{ severityMeta(fail.severity).label }}
                  </v-chip>
                  <v-icon icon="mdi-chevron-right" size="small" class="ml-2" />
                </template>
              </v-list-item>
            </v-list>
          </v-card>
        </template>
      </template>

      <!-- ================================================================ -->
      <!-- Sticky CTA — baseline runs with failures                          -->
      <!-- ================================================================ -->
      <div
        v-if="isBaseline && failedCount > 0 && run && run.executed > 0"
        class="sticky-cta"
      >
        <v-card variant="flat" class="pa-3" elevation="8">
          <div class="d-flex align-center justify-center ga-3">
            <span class="text-body-2 font-weight-medium">
              {{ failedCount }} attack{{ failedCount !== 1 ? 's' : '' }} got through — enable protection and re-run to verify
            </span>
            <v-btn
              v-if="isDemoTarget"
              color="primary"
              variant="flat"
              size="small"
              prepend-icon="mdi-shield-check"
              class="cta-pulse"
              :loading="isRerunning"
              @click="onRerunProtected"
            >
              Enable protection &amp; re-run
            </v-btn>
            <v-btn
              v-else
              color="primary"
              variant="flat"
              size="small"
              prepend-icon="mdi-shield-plus"
              class="cta-pulse"
              @click="showSetupDialog = true"
            >
              Set up protection
            </v-btn>
          </div>
        </v-card>
      </div>

      <!-- ================================================================ -->
      <!-- Protect this endpoint — dialog                                    -->
      <!-- ================================================================ -->
      <v-dialog v-model="showSetupDialog" max-width="780" scrollable>
        <v-card>
          <!-- Title -->
          <v-card-title class="d-flex align-center pt-5 pb-2 px-6">
            <v-icon icon="mdi-shield-half-full" color="primary" size="small" class="mr-2" />
            Protect this endpoint
          </v-card-title>

          <!-- Context summary -->
          <div class="px-6 pb-3">
            <v-card variant="tonal" color="surface-variant" class="pa-3 rounded">
              <div class="d-flex flex-column ga-1 text-caption">
                <div class="d-flex align-center ga-2">
                  <span class="text-medium-emphasis" style="min-width: 64px;">Endpoint</span>
                  <code class="text-truncate" style="max-width: 480px;">{{ targetEndpointUrl || 'your LLM endpoint' }}</code>
                </div>
                <div class="d-flex align-center ga-2">
                  <span class="text-medium-emphasis" style="min-width: 64px;">Pack</span>
                  <span>{{ humanPack(run.pack) }}</span>
                </div>
                <div class="d-flex align-center ga-2">
                  <span class="text-medium-emphasis" style="min-width: 64px;">Baseline</span>
                  <span class="text-error font-weight-medium">{{ allFailures.length }} attack{{ allFailures.length === 1 ? '' : 's' }} got through — re-run to verify which are now blocked</span>
                </div>
              </div>
            </v-card>
          </div>

          <!-- Intro -->
          <p class="text-body-2 text-medium-emphasis px-6 pb-3 mb-0">
            AI Protector inspects every request before it reaches the model. Blocked attacks never hit the LLM.
            Choose the integration that fits your API format:
          </p>

          <v-divider />

          <v-card-text class="pa-6">

            <!-- ── Integration Option A: OpenAI-compatible ── -->
            <div class="setup-step mb-5">
              <div class="d-flex align-center mb-2">
                <v-chip color="primary" variant="flat" size="x-small" label class="mr-3 font-weight-bold">Option A</v-chip>
                <span class="text-subtitle-2 font-weight-bold">OpenAI-compatible APIs</span>
                <v-chip color="success" variant="tonal" size="x-small" class="ml-2">Drop-in</v-chip>
              </div>
              <p class="text-body-2 text-medium-emphasis mb-3 pl-1">
                If your backend calls an OpenAI-compatible endpoint (<code>/v1/chat/completions</code>),
                just swap the base URL to point at AI Protector. It acts as a transparent proxy —
                inspects the request, blocks attacks, and forwards clean requests to your original model.
              </p>

              <!-- How it works diagram -->
              <v-card variant="outlined" class="url-diff-card pa-3 mb-3">
                <div class="text-caption text-medium-emphasis mb-2 font-weight-medium">How it works</div>
                <div class="d-flex align-center flex-wrap ga-2 mb-2" style="font-family: monospace; font-size: 0.8rem;">
                  <span>Your app</span>
                  <v-icon icon="mdi-arrow-right" size="x-small" />
                  <span class="url-proxy-highlight">{{ protectedHost }}/v1/chat/completions</span>
                  <v-icon icon="mdi-arrow-right" size="x-small" />
                  <span class="text-medium-emphasis">inspect &amp; filter</span>
                  <v-icon icon="mdi-arrow-right" size="x-small" />
                  <span>Original LLM</span>
                </div>
                <v-divider class="my-2" />
                <div class="text-caption text-medium-emphasis">
                  Replace <code>https://api.openai.com</code> (or any compatible host) with
                  <code>{{ protectedHost }}</code> in your <code>.env</code>, SDK config, or deployment manifest.
                  Keep the same path — only the host changes.
                </div>
              </v-card>

              <div class="d-flex align-center ga-2">
                <v-btn
                  :color="urlCopied ? 'success' : 'primary'"
                  :variant="urlCopied ? 'tonal' : 'outlined'"
                  size="small"
                  :prepend-icon="urlCopied ? 'mdi-check' : 'mdi-content-copy'"
                  @click="copyProtectedUrl"
                >
                  {{ urlCopied ? 'Copied!' : 'Copy proxy URL' }}
                </v-btn>
                <span class="text-caption text-medium-emphasis">{{ protectedBaseUrl }}</span>
              </div>
            </div>

            <v-divider class="mb-5" />

            <!-- ── Integration Option B: Non-OpenAI / custom APIs ── -->
            <div class="setup-step mb-5">
              <div class="d-flex align-center mb-2">
                <v-chip color="secondary" variant="flat" size="x-small" label class="mr-3 font-weight-bold">Option B</v-chip>
                <span class="text-subtitle-2 font-weight-bold">Other API formats</span>
              </div>
              <p class="text-body-2 text-medium-emphasis mb-3 pl-1">
                For non-OpenAI APIs (custom REST, gRPC, proprietary SDKs), use the <strong>scan-only endpoint</strong>
                as a pre-check in your code. Send the prompt to <code>/v1/scan</code> first — if the verdict is
                <code>ALLOW</code>, forward it to your model; if <code>BLOCK</code>, reject it before it ever
                reaches the LLM.
              </p>

              <v-card variant="outlined" class="url-diff-card pa-3 mb-3">
                <div class="text-caption text-medium-emphasis mb-2 font-weight-medium">Example: pre-check in code</div>
                <pre class="text-caption" style="white-space: pre-wrap; margin: 0; line-height: 1.6;"><code>POST {{ protectedHost }}/v1/scan
{
  "messages": [{"role": "user", "content": "...user prompt..."}]
}

→ 200  { "decision": "ALLOW", ... }   # safe — call your LLM
→ 403  { "decision": "BLOCK", ... }   # attack — reject the request</code></pre>
              </v-card>

              <p class="text-caption text-medium-emphasis mb-0 pl-1">
                <v-icon icon="mdi-information-outline" size="12" class="mr-1" />
                The scan endpoint runs the full firewall pipeline (intent analysis, rules, PII scanners)
                but does not call any LLM — no extra latency or cost beyond the inspection itself.
              </p>
            </div>

            <v-divider class="mb-5" />

            <!-- After integration: restart + re-scan -->
            <div class="setup-step setup-step--warning mb-5">
              <div class="d-flex align-center mb-1">
                <div class="step-number step-number--warning mr-3">!</div>
                <span class="text-subtitle-2 font-weight-bold">Restart your backend after the change</span>
                <v-chip color="warning" variant="tonal" size="x-small" class="ml-2">Don't skip</v-chip>
              </div>
              <p class="text-body-2 text-medium-emphasis mb-0 pl-9">
                If you skip this, the old endpoint may still be active. The next scan will look unprotected even if you changed the config.
              </p>
            </div>

            <div class="setup-step mb-5">
              <div class="d-flex align-center mb-1">
                <v-icon icon="mdi-reload" color="primary" size="small" class="mr-3" />
                <span class="text-subtitle-2 font-weight-bold">Run the protected re-scan</span>
              </div>
              <p class="text-body-2 text-medium-emphasis mb-0 pl-9">
                Use the button below once your backend is live on the protected URL. This re-runs the exact same pack for a trustworthy before-vs-after comparison.
              </p>
            </div>

            <!-- Info box -->
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              <div class="text-caption">
                Backend change only &nbsp;·&nbsp; No frontend changes needed &nbsp;·&nbsp; <strong>Typical setup: 5–15 min</strong>
              </div>
            </v-alert>

            <!-- Troubleshooting note -->
            <p class="text-caption text-medium-emphasis mb-0">
              <v-icon icon="mdi-information-outline" size="12" class="mr-1" />
              Still seeing unprotected results? Your backend likely didn't restart with the new endpoint.
            </p>

          </v-card-text>

          <v-divider />

          <v-card-actions class="pa-4">
            <a class="text-caption text-medium-emphasis" style="cursor: pointer;" @click="showSetupDialog = false">Close</a>
            <v-spacer />
            <v-btn
              color="primary"
              variant="flat"
              prepend-icon="mdi-shield-check"
              :loading="isRerunning"
              data-testid="setup-dialog-rerun-btn"
              @click="showSetupDialog = false; onRerun()"
            >
              Backend updated — run protected re-scan
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>

    <!-- Error state -->
    <v-alert v-else type="error" variant="tonal" class="mt-4">
      Could not load benchmark results.
    </v-alert>
  </v-container>
</template>

<script setup lang="ts">
import { benchmarkService } from '~/services/benchmarkService'
import type { RunDetail, ScenarioResult, CompareResult } from '~/services/benchmarkService'
import { humanCategory, severityMeta, humanPack, scoreLabel, baselineScoreLabel, classifyRun } from '~/utils/redTeamLabels'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()
const runId = computed(() => route.params.id as string)

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const loading = ref(true)
const run = ref<RunDetail | null>(null)
const scenarios = ref<ScenarioResult[]>([])
const comparison = ref<CompareResult | null>(null)
const showSetupDialog = ref(false)
const policyApplied = ref(false)
const _rerunPolicy = ref('Strict')
const isRerunning = ref(false)
const isExporting = ref(false)
const showAllFailures = ref(false)
const urlCopied = ref(false)
let _urlCopiedTimer: ReturnType<typeof setTimeout> | null = null

// ---------------------------------------------------------------------------
// Computed — target label
// ---------------------------------------------------------------------------

const TARGET_LABELS: Record<string, { label: string; icon: string }> = {
  demo_agent: { label: 'Demo Endpoint', icon: 'mdi-robot-outline' },
  demo: { label: 'Demo Endpoint', icon: 'mdi-robot-outline' },
  registered_agent: { label: 'Registered Endpoint', icon: 'mdi-shield-check' },
  local_agent: { label: 'Local Endpoint', icon: 'mdi-laptop' },
  hosted_endpoint: { label: 'Your Endpoint', icon: 'mdi-cloud-outline' },
}

const targetMeta = computed(() => TARGET_LABELS[run.value?.target_type ?? ''] ?? { label: run.value?.target_type ?? 'Agent', icon: 'mdi-robot-outline' })
const targetLabel = computed(() => targetMeta.value.label)
const targetIcon = computed(() => targetMeta.value.icon)

// ---------------------------------------------------------------------------
// Computed — run classification (baseline vs protected)
// ---------------------------------------------------------------------------

const runClass = computed(() => run.value ? classifyRun(run.value) : null)
const isBaseline = computed(() => runClass.value?.type === 'baseline')
const isDemoTarget = computed(() => {
  const t = run.value?.target_type ?? ''
  return t === 'demo' || t === 'demo_agent'
})

// ---------------------------------------------------------------------------
// Computed — dynamic page title
// ---------------------------------------------------------------------------

const pageTitle = computed(() => {
  if (!run.value) return ''
  if (!isBaseline.value) {
    return failedCount.value === 0
      ? 'Protected re-run: all attacks blocked'
      : 'Protected re-run: verified improvement'
  }
  if (failedCount.value > 0) {
    return `${failedCount.value} attack${failedCount.value !== 1 ? 's' : ''} got through`
  }
  return 'Baseline scan complete'
})

// ---------------------------------------------------------------------------
// Computed — score (uses baseline labels for unprotected runs)
// ---------------------------------------------------------------------------

const scoreMeta = computed(() => {
  const score = run.value?.score_simple ?? 0
  return isBaseline.value ? baselineScoreLabel(score) : scoreLabel(score)
})

const criticalCount = computed(() => {
  return scenarios.value.filter(
    (s) => s.passed === false && (s.severity === 'critical' || s.severity === 'high'),
  ).length
})

const failedCount = computed(() => {
  return scenarios.value.filter((s) => s.passed === false).length
})

const _safeOutcomeCount = computed(() => {
  // For baseline runs: safe outcomes = passed count
  // We cannot attribute whether safe outcomes came from model resistance or no-breach;
  // show the combined number with a clear label.
  return run.value?.passed ?? 0
})

const skippedMutating = computed(() => {
  return run.value?.skipped_reasons?.safe_mode ?? 0
})

// ---------------------------------------------------------------------------
// Failure impact hints — short risk descriptions
// ---------------------------------------------------------------------------

const CATEGORY_IMPACT: Record<string, string> = {
  prompt_injection_jailbreak: 'Could expose system prompt or bypass instructions',
  data_leakage_pii: 'May leak sensitive data or PII in responses',
  tool_abuse: 'Could trigger unauthorized tool calls',
  access_control: 'Bypasses role or permission boundaries',
}

function failureImpact(fail: ScenarioResult): string {
  if (fail.severity === 'critical' || fail.severity === 'high') {
    return CATEGORY_IMPACT[fail.category] ?? 'Likely to recur in production'
  }
  return ''
}

// Mitigation label — tells user which ones are easy to fix
const CATEGORY_MITIGATION: Record<string, string> = {
  prompt_injection_jailbreak: 'Can be mitigated by strict profile',
  data_leakage_pii: 'Can be mitigated by strict profile',
  tool_abuse: 'Needs custom rule',
  access_control: 'Needs custom rule',
}

const BASELINE_CATEGORY_MITIGATION: Record<string, string> = {
  prompt_injection_jailbreak: 'Can be mitigated by strict profile',
  data_leakage_pii: 'Can be mitigated by strict profile',
  tool_abuse: 'Can be mitigated by custom rule',
  access_control: 'Can be mitigated by custom rule',
}

function failureMitigation(fail: ScenarioResult): string {
  if (isBaseline.value) {
    return BASELINE_CATEGORY_MITIGATION[fail.category] ?? ''
  }
  return CATEGORY_MITIGATION[fail.category] ?? ''
}

const targetEndpointUrl = computed(() => {
  return run.value?.target_config?.endpoint_url ?? ''
})

// True if this run originally had auth headers (now deleted from DB)
const hadAuth = computed(() => !!run.value?.target_config?._had_auth)

// Build redirect query for re-run when the token needs to be re-entered
function rerunQuery(opts: { protected?: boolean } = {}) {
  const r = run.value!
  const q: Record<string, string> = {
    type: r.target_type,
    url: targetEndpointUrl.value,
    pack: r.pack,
    policy: opts.protected ? 'balanced' : (r.policy ?? 'balanced'),
    reauth: 'true',
  }
  if (opts.protected) q.protected = 'true'
  return q
}

const timeAgo = computed(() => {
  if (!run.value?.completed_at && !run.value?.created_at) return ''
  const ts = run.value.completed_at ?? run.value.created_at
  if (!ts) return ''
  const diff = Math.round((Date.now() - new Date(ts).getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
})

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-GB', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  })
}

const durationLabel = computed(() => {
  if (!run.value?.created_at || !run.value?.completed_at) return ''
  const ms = new Date(run.value.completed_at).getTime() - new Date(run.value.created_at).getTime()
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`
})

// ---------------------------------------------------------------------------
// Computed — category bars (human-readable names)
// ---------------------------------------------------------------------------

const categoryBars = computed(() => {
  const groups = new Map<string, { passed: number; total: number }>()
  for (const s of scenarios.value) {
    if (s.skipped) continue
    const cat = s.category || 'uncategorized'
    const g = groups.get(cat) ?? { passed: 0, total: 0 }
    g.total++
    if (s.passed) g.passed++
    groups.set(cat, g)
  }

  return Array.from(groups.entries())
    .map(([slug, g]) => ({
      slug,
      label: humanCategory(slug),
      passedCount: g.passed,
      total: g.total,
      percent: g.total > 0 ? Math.round((g.passed / g.total) * 100) : 0,
    }))
    .sort((a, b) => a.percent - b.percent) // worst first
})

// ---------------------------------------------------------------------------
// Computed — top failures (with enriched fields)
// ---------------------------------------------------------------------------

const severityWeight: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
}

const topFailures = computed(() => {
  const sorted = scenarios.value
    .filter((s) => s.passed === false)
    .sort((a, b) => (severityWeight[a.severity] ?? 9) - (severityWeight[b.severity] ?? 9))
  return showAllFailures.value ? sorted : sorted.slice(0, 5)
})

const allFailures = computed(() => {
  return scenarios.value.filter((s) => s.passed === false)
})

/** Number of failures in the baseline run (from comparison data) */
const baselineFailedCount = computed(() => {
  if (!comparison.value) return 0
  const baseScore = comparison.value.run_a
  return (baseScore.executed ?? 0) - (baseScore.passed ?? 0)
})

// ---------------------------------------------------------------------------
// CTA actions
// ---------------------------------------------------------------------------

const protectedBaseUrl = computed(() => {
  const base = (import.meta.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000').replace(/\/+$/, '')
  return `${base}/v1/chat/completions`
})

const protectedHost = computed(() => {
  try {
    const u = new URL(protectedBaseUrl.value)
    return u.host
  } catch {
    return protectedBaseUrl.value
  }
})

async function copyProtectedUrl() {
  try {
    await navigator.clipboard.writeText(protectedBaseUrl.value)
  } catch {
    // Fallback: select the text
  }
  urlCopied.value = true
  if (_urlCopiedTimer) clearTimeout(_urlCopiedTimer)
  _urlCopiedTimer = setTimeout(() => { urlCopied.value = false }, 2500)
}

async function onRerun() {
  if (!run.value) return
  // If the run had auth headers (now deleted), redirect to the form to re-enter them
  if (hadAuth.value) {
    router.push({ path: '/red-team/target', query: rerunQuery() })
    return
  }
  isRerunning.value = true
  try {
    const result = await benchmarkService.createRun({
      target_type: run.value.target_type,
      target_config: run.value.target_config,
      pack: run.value.pack,
      policy: policyApplied.value ? 'strict' : (run.value.policy ?? 'balanced'),
      source_run_id: run.value.id,
    })
    router.push(`/red-team/run/${result.id}`)
  } catch {
    isRerunning.value = false
  }
}

async function onRerunProtected() {
  if (!run.value) return
  // If the run had auth headers (now deleted), redirect to the form to re-enter them
  if (hadAuth.value) {
    router.push({ path: '/red-team/target', query: rerunQuery({ protected: true }) })
    return
  }
  isRerunning.value = true
  try {
    const config = { ...(run.value.target_config ?? {}), through_proxy: true }
    const result = await benchmarkService.createRun({
      target_type: run.value.target_type,
      target_config: config,
      pack: run.value.pack,
      policy: 'balanced',
      source_run_id: run.value.id,
    })
    router.push(`/red-team/run/${result.id}`)
  } catch {
    isRerunning.value = false
  }
}

function onExport() {
  if (!run.value) return
  isExporting.value = true
  benchmarkService.exportRun(run.value.id, 'pdf')
    .then((blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `security-audit-${run.value!.id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    })
    .catch(() => {
      // Fallback: client-side JSON export if PDF endpoint unavailable
      onExportJson()
    })
    .finally(() => {
      isExporting.value = false
    })
}

function onExportJson() {
  if (!run.value) return
  const r = run.value
  const report = {
    exported_at: new Date().toISOString(),
    run: {
      id: r.id,
      target_type: r.target_type,
      pack: r.pack,
      status: r.status,
      score_simple: r.score_simple,
      score_weighted: r.score_weighted,
      total_in_pack: r.total_in_pack,
      total_applicable: r.total_applicable,
      executed: r.executed,
      passed: r.passed,
      failed: r.failed,
      skipped: r.skipped,
      skipped_reasons: r.skipped_reasons,
      protection_detected: r.protection_detected,
      proxy_blocked_count: r.proxy_blocked_count,
      policy: r.policy,
      source_run_id: r.source_run_id,
      created_at: r.created_at,
      completed_at: r.completed_at,
    },
    summary: {
      duration_s: r.created_at && r.completed_at
        ? Math.round((new Date(r.completed_at).getTime() - new Date(r.created_at).getTime()) / 1000)
        : null,
      avg_latency_ms: (() => {
        const lats = scenarios.value.filter((s) => s.latency_ms != null).map((s) => s.latency_ms!)
        return lats.length ? Math.round(lats.reduce((a, b) => a + b, 0) / lats.length) : null
      })(),
      critical_failures: scenarios.value.filter((s) => !s.passed && s.severity === 'critical').length,
      high_failures: scenarios.value.filter((s) => !s.passed && s.severity === 'high').length,
    },
    categories: categoryBars.value,
    scenarios: scenarios.value.map((s) => {
      const entry: Record<string, unknown> = {
        scenario_id: s.scenario_id,
        title: s.title,
        category: s.category,
        severity: s.severity,
        passed: s.passed,
        expected: s.expected,
        actual: s.actual,
        latency_ms: s.latency_ms,
        prompt: s.prompt,
      }
      if (s.description) entry.description = s.description
      if (s.detector_type) entry.detector_type = s.detector_type
      if (s.skipped) {
        entry.skipped = true
        if (s.skipped_reason) entry.skipped_reason = s.skipped_reason
      }
      if (!s.passed && s.fix_hints?.length) entry.fix_hints = s.fix_hints
      if (!s.passed && s.why_it_passes) entry.why_it_passes = s.why_it_passes
      if (s.detector_detail && Object.keys(s.detector_detail).length) entry.detector_detail = s.detector_detail
      return entry
    }),
    ...(comparison.value ? { comparison: {
      source_run_id: comparison.value.run_a_id,
      score_delta: comparison.value.score_delta,
      weighted_delta: comparison.value.weighted_delta,
      fixed_failures: comparison.value.fixed_failures,
      new_failures: comparison.value.new_failures,
    } } : {}),
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `security-audit-${run.value.id}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

async function fetchData() {
  loading.value = true
  try {
    const [runData, scenariosData] = await Promise.all([
      benchmarkService.getRun(runId.value),
      benchmarkService.getScenarios(runId.value),
    ])
    run.value = runData
    scenarios.value = scenariosData

    if (runData.source_run_id) {
      try {
        comparison.value = await benchmarkService.compareRuns(runData.source_run_id, runData.id)
      } catch {
        // Comparison is optional
      }
    }
  } catch {
    run.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.score-badge {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 5px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.score-value {
  font-size: 1.8rem;
  font-weight: 700;
  line-height: 1;
}

// ── Setup dialog styles ──────────────────────────────────────────────────

// (in <style> block below)

.sticky-cta {
  position: sticky;
  bottom: 16px;
  z-index: 10;
  margin-top: 16px;

  .v-card {
    box-shadow:
      0 8px 32px rgba(0, 0, 0, 0.7),
      0 0 24px rgba(var(--v-theme-primary), 0.35),
      0 0 8px rgba(var(--v-theme-primary), 0.2) !important;
    border: 1px solid rgba(var(--v-theme-primary), 0.4) !important;
  }
}

@keyframes cta-glow-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(var(--v-theme-primary), 0.55);
    transform: scale(1);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(var(--v-theme-primary), 0);
    transform: scale(1.03);
  }
}

.cta-pulse {
  animation: cta-glow-pulse 2s ease-in-out infinite;
}

// ── Setup dialog ────────────────────────────────────────────────────────

.setup-step {
  position: relative;
}

.setup-step--warning {
  border-left: 3px solid rgb(var(--v-theme-warning));
  padding-left: 12px;
  margin-left: -12px;
}

.step-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.15);
  color: rgb(var(--v-theme-primary));
  font-size: 0.75rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-number--warning {
  background: rgba(var(--v-theme-warning), 0.15);
  color: rgb(var(--v-theme-warning));
}

.url-diff-card {
  border-color: rgba(var(--v-theme-outline), 0.3);
}

.url-diff-label {
  min-width: 44px;
  display: inline-block;
  flex-shrink: 0;
}

.url-before {
  text-decoration: line-through;
  opacity: 0.55;
}

.url-proxy-highlight {
  background: rgba(var(--v-theme-primary), 0.15);
  color: rgb(var(--v-theme-primary));
  border-radius: 3px;
  padding: 1px 4px;
  font-weight: 600;
}
</style>
