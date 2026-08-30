<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api } from "../api";
import type { IssueProposalPreviewData, IssueRecord, LinkedPhoto, PhotoAnalysisRecord, PhotoMetadata, VisionRuntime } from "../types";

const props = defineProps<{ record: IssueRecord | null; evidenceOnly?: boolean }>();
const emit = defineEmits<{ proposal: [data: IssueProposalPreviewData]; busy: [value: boolean] }>();
const runtime = ref<VisionRuntime | null>(null);
const selected = ref<File | null>(null);
const uploadAuthorized = ref(false);
const externalConsent = ref(false);
const photo = ref<PhotoMetadata | null>(null);
const analysis = ref<PhotoAnalysisRecord | null>(null);
const context = ref("请初步核对图片中的可见情况，无法确认的内容请追问。");
const busy = ref(false);
const error = ref("");
const notice = ref("");
const links = ref<LinkedPhoto[]>([]);
const stage = ref<"before" | "after">("before");
const summaries = reactive<Record<string, string>>({});
const notes = reactive<Record<string, string>>({});
const reviewed = reactive<Record<string, boolean>>({});
let generation = 0;

const canAnalyze = computed(() => photo.value && runtime.value?.configured && !busy.value
  && (runtime.value.mode === "mock" || externalConsent.value));
const canLink = computed(() => photo.value && !busy.value && props.record?.disposition === "active"
  && (stage.value === "before" ? ["draft", "submitted", "assigned"] : ["rectifying", "pending_review"]).includes(props.record.status));

onMounted(async () => {
  try { runtime.value = await api.getVisionRuntime(); }
  catch { error.value = "图片服务尚未连接，仍可使用文字验收入口。"; }
});

watch(context, () => { externalConsent.value = false; });
watch(busy, value => emit("busy", value), { flush: "sync" });
watch(stage, () => { error.value = ""; notice.value = ""; });
watch(() => props.record, async (record) => {
  const id = record?.record_id;
  links.value = [];
  notice.value = "";
  if (!id) return;
  try {
    const result = await api.getRecordPhotos(id);
    if (props.record?.record_id === id) links.value = result;
  } catch { error.value = "图片关联列表无法加载，不影响文字记录。"; }
}, { deep: true, immediate: true });

function selectFile(event: Event) {
  const files = (event.target as HTMLInputElement).files;
  generation += 1;
  selected.value = null;
  photo.value = null;
  analysis.value = null;
  uploadAuthorized.value = false;
  externalConsent.value = false;
  error.value = "";
  notice.value = "";
  if (!files?.length) return;
  if (files.length !== 1 || !["image/jpeg", "image/png"].includes(files[0].type) || files[0].size > 5 * 1024 * 1024) {
    error.value = "请选择一张不超过5MiB的JPEG/PNG图片。";
    return;
  }
  selected.value = files[0];
}

async function upload() {
  if (!selected.value || !uploadAuthorized.value) return;
  const current = generation;
  busy.value = true; error.value = ""; notice.value = "";
  try {
    const result = await api.uploadPhoto(selected.value);
    if (current === generation) photo.value = result;
  } catch (cause) { if (current === generation) error.value = String(cause); }
  finally { busy.value = false; }
}

async function analyze() {
  if (!photo.value || !canAnalyze.value) return;
  const current = generation;
  busy.value = true; error.value = ""; analysis.value = null; notice.value = "";
  try {
    const result = await api.analyzePhoto(photo.value.photo_id, context.value, externalConsent.value);
    if (current !== generation) return;
    analysis.value = result;
    for (const candidate of result.result.candidates) {
      summaries[candidate.candidate_id] = candidate.analysis.summary;
      notes[candidate.candidate_id] = "";
      reviewed[candidate.candidate_id] = false;
    }
  } catch (cause) { if (current === generation) error.value = String(cause); }
  finally { busy.value = false; externalConsent.value = false; }
}

async function decide(candidateId: string, decision: "accept" | "reject") {
  if (!analysis.value) return;
  if (!notes[candidateId]?.trim()) { error.value = "请填写人工核对或纠正说明。"; return; }
  busy.value = true; error.value = ""; notice.value = "";
  try {
    const result = await api.decidePhotoCandidate(analysis.value.analysis_id, candidateId, decision, summaries[candidateId], notes[candidateId]);
    if (!result.ok) throw new Error(result.summary);
    reviewed[candidateId] = true;
    notice.value = decision === "accept" ? "候选已采纳，上方生成待确认提案；尚未创建记录或关联照片。" : "候选已驳回并留痕，未创建提案。";
    if (decision === "accept") emit("proposal", result.data);
  } catch (cause) { error.value = String(cause); }
  finally { busy.value = false; }
}

async function link() {
  if (!props.record || !photo.value) return;
  busy.value = true; error.value = ""; notice.value = "";
  const record = props.record;
  try {
    await api.linkPhoto(record, photo.value.photo_id, stage.value);
    const result = await api.getRecordPhotos(record.record_id);
    if (props.record?.record_id === record.record_id) links.value = result;
    notice.value = "照片已关联；问题状态、风险和revision均未改变。";
  } catch (cause) { error.value = String(cause); }
  finally { busy.value = false; }
}

const observationLabels = { observed: "观察到", uncertain: "不确定", not_observed: "未观察到" };
const limitationLabels: Record<string, string> = { low_resolution: "分辨率较低", blurred: "模糊", occluded: "遮挡", context_missing: "缺少上下文" };
</script>

<template>
  <section class="image-panel" aria-labelledby="image-title">
    <div class="section-heading"><div><p class="eyebrow">Phase 5 · 单张图片证据</p><h2 id="image-title">先观察，再由人确认</h2></div>
      <span class="warning-chip">图片不是最终认定</span></div>
    <p v-if="runtime">图片模式：{{ runtime.mode }} · {{ runtime.model }} · {{ runtime.configured ? "已配置" : "配置未就绪" }}</p>
    <p class="section-note">仅一张JPEG/PNG，最大5MiB、每边4096像素。EXIF清除不会遮挡人脸、工牌或项目铭牌，请先自行打码。图片失败时可继续上方文字流程。</p>
    <label>选择单张图片<input type="file" accept="image/jpeg,image/png" :disabled="busy" @change="selectFile" /></label>
    <label class="consent"><input v-model="uploadAuthorized" type="checkbox" :disabled="busy" />我确认图片已打码且有权上传到本地项目</label>
    <button class="secondary-button" :disabled="!selected || !uploadAuthorized || busy" @click="upload">上传并清除元数据</button>
    <div v-if="photo" class="photo-preview">
      <img :src="api.photoContentUrl(photo.photo_id)" alt="服务器清除元数据后的图片预览" />
      <p>{{ photo.photo_id }} · {{ photo.width }}×{{ photo.height }} · 元数据已清除</p>
    </div>
    <p v-if="evidenceOnly" class="section-note">详情页用于关联本工单的照片证据；分析新的图片问题请前往“咨询与上报”。</p>
    <template v-if="!evidenceOnly">
    <label>图片补充描述<textarea v-model.trim="context" maxlength="1000" rows="3" :disabled="busy"></textarea></label>
    <label v-if="runtime?.mode === 'real'" class="consent"><input v-model="externalConsent" type="checkbox" :disabled="busy" />本次允许将脱敏图片和补充描述发送至DeepSeek，理解会产生模型费用</label>
    <button class="primary-button" :disabled="!canAnalyze" @click="analyze">{{ busy ? "处理中…" : runtime?.mode === "real" ? "确认本次费用并分析图片" : "运行Mock图片链路（不识别内容）" }}</button>
    </template>
    <p v-if="error" role="alert" class="error-message">{{ error }}</p>
    <p v-if="notice" role="status" class="info-callout">{{ notice }}</p>
    <div v-if="analysis && !evidenceOnly" class="visual-results" aria-live="polite">
      <h3>初步视觉结果 · 必须人工复核</h3>
      <p>本次模式：{{ analysis.mode }}；未观察到不等于不存在。</p>
      <ul><li v-for="item in analysis.result.observations" :key="item.observation_id"><strong>{{ observationLabels[item.status] }}</strong>：{{ item.description }}</li></ul>
      <p v-if="analysis.result.limitations.length">图像限制：{{ analysis.result.limitations.map(value => limitationLabels[value]).join('、') }}</p>
      <ul><li v-for="question in analysis.result.follow_up_questions" :key="question">需补充：{{ question }}</li></ul>
      <p v-if="!analysis.result.candidates.length">没有可采纳的施工问题候选；这不代表现场安全或质量合格。</p>
      <article v-for="candidate in analysis.result.candidates" :key="candidate.candidate_id" class="candidate-card">
        <h4>{{ candidate.candidate_id }} · {{ candidate.analysis.issue_type }} · {{ candidate.analysis.risk_level }}</h4>
        <p v-for="action in candidate.analysis.immediate_actions" :key="action" class="error-message">{{ action }}</p>
        <p>不确定性：{{ candidate.analysis.uncertainties.join('；') }}</p>
        <p>必须补充：{{ candidate.analysis.missing_fields.join('；') }}</p>
        <label>人工核对后的摘要<textarea v-model.trim="summaries[candidate.candidate_id]" maxlength="500" :disabled="busy || reviewed[candidate.candidate_id]"></textarea></label>
        <label>核对或纠正说明<textarea v-model.trim="notes[candidate.candidate_id]" maxlength="300" :disabled="busy || reviewed[candidate.candidate_id]"></textarea></label>
        <p class="section-note">纠正摘要不会降低风险或取消人工复核；采纳会在上方替换当前提案草稿，不改已有记录。</p>
        <div class="button-row"><button class="primary-button" :disabled="busy || reviewed[candidate.candidate_id]" @click="decide(candidate.candidate_id, 'accept')">人工采纳并生成待确认提案</button>
          <button class="secondary-button" :disabled="busy || reviewed[candidate.candidate_id]" @click="decide(candidate.candidate_id, 'reject')">驳回此候选</button></div>
      </article>
    </div>
    <div v-if="record" class="photo-links">
      <h3>关联到 {{ record.record_id }} 的照片证据</h3>
      <p class="section-note">前照片由原报告人在整改开始前关联；后照片由已指派整改人在整改中/待复查阶段关联。演示角色无生产身份认证。</p>
      <label>照片阶段<select v-model="stage"><option value="before">整改前</option><option value="after">整改后（不表示复查通过）</option></select></label>
      <button class="secondary-button" :disabled="!canLink" @click="link">人工确认关联当前照片</button>
      <p v-if="!canLink" class="section-note">请先上传图片，并确认当前记录阶段允许关联此类照片；关闭或取消后不能追加。</p>
      <div class="linked-grid"><article v-for="item in links" :key="item.photo.photo_id">
        <img :src="api.photoContentUrl(item.photo.photo_id)" :alt="item.link.stage === 'before' ? '整改前照片' : '整改后照片'" />
        <p>{{ item.link.stage === "before" ? "整改前" : "整改后" }} · 关联时revision {{ item.link.record_revision }}</p>
        <small>{{ item.photo.photo_id }}</small>
      </article></div>
    </div>
  </section>
</template>

<style scoped>
.image-panel { margin-top: 24px; padding: 28px; background: white; border: 1px solid #d9e2ed; border-radius: 18px; }
.image-panel label { display: grid; gap: 8px; margin: 16px 0; }
.image-panel .consent { display: flex; align-items: flex-start; line-height: 1.6; }
.consent input { width: auto; margin-top: 5px; }
.photo-preview img { display: block; max-width: 100%; max-height: 280px; margin-top: 18px; object-fit: contain; }
.candidate-card { margin: 16px 0; padding: 18px; background: #f4f7fb; border-radius: 12px; }
.linked-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-top: 16px; }
.linked-grid img { width: 100%; height: 180px; object-fit: contain; }
.image-panel p, .image-panel small { overflow-wrap: anywhere; }
@media (max-width: 600px) { .image-panel { padding: 18px; } .section-heading { flex-direction: column; align-items: flex-start; gap: 10px; } }
</style>
