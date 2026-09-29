export const meta = {
  name: 'mock-exam',
  description: 'Persona students sit an exam, blind graders mark it, analysts review it, and a dashboard is built',
  whenToUse: 'Pilot a new exam before real students see it. Args: the exam id (a folder under exams/), or {exam, personas, label}.',
  phases: [
    { title: 'Prepare', detail: 'run folder, anonymous ids, materials per persona' },
    { title: 'Sit', detail: 'one student agent per persona' },
    { title: 'Grade', detail: 'one blind grader per answer sheet' },
    { title: 'Analyze', detail: 'statistics, feedback synthesis, exam review' },
    { title: 'Report', detail: 'dashboard.html' },
  ],
}

// Claude usually passes {exam, personas, label}; a bare string is taken as the exam id.
const opts = typeof args === 'string'
  ? (args.trim().startsWith('{') ? JSON.parse(args) : { exam: args.trim() })
  : (args || {})
if (!opts.exam) throw new Error('Pass the exam id, e.g. /mock-exam example')

const STR = { type: 'string' }
const NUM = { type: 'number' }
const PREPARED = {
  type: 'object',
  properties: {
    error: STR,
    manifest: {
      type: 'object',
      required: ['run_dir', 'exam', 'students'],
      properties: {
        run_dir: STR,
        exam: {
          type: 'object',
          required: ['title', 'duration_min', 'student_file', 'solution_files', 'total_points', 'questions'],
          properties: {
            title: STR, duration_min: NUM, aids: STR, language: STR, student_file: STR, total_points: NUM, typical_score: NUM,
            solution_files: { type: 'array', items: STR },
            questions: { type: 'array', items: { type: 'object', required: ['id', 'points'], properties: { id: STR, points: NUM } } },
          },
        },
        students: {
          type: 'array',
          items: {
            type: 'object',
            required: ['sid', 'persona_file', 'model', 'materials'],
            properties: { sid: STR, persona_file: STR, model: STR, materials: { type: 'array', items: STR } },
          },
        },
      },
    },
  },
}
const SAT = {
  type: 'object',
  required: ['sid', 'answered', 'partial', 'blank', 'minutes_used'],
  properties: { sid: STR, answered: { type: 'integer' }, partial: { type: 'integer' }, blank: { type: 'integer' }, minutes_used: NUM },
}
const GRADED = { type: 'object', required: ['sid', 'total', 'max_total'], properties: { sid: STR, total: NUM, max_total: NUM } }

const runScript = (cmd, label, phase) => agent(
  `From the project root, run exactly this command and return its output unchanged:\n\n${cmd}`,
  { label, phase, model: 'haiku', effort: 'low' },
)

phase('Prepare')
const flags = [
  opts.personas && `--personas ${[].concat(opts.personas).join(',')}`,
  opts.label && `--label ${opts.label}`,
].filter(Boolean).join(' ')
const prepared = await agent(
  `From the project root, run exactly:\n\npython3 scripts/prepare_run.py --exam ${opts.exam} ${flags}\n\n` +
  'On success it prints one JSON object: return it as `manifest`, unchanged. On failure, return the error message as `error`.',
  { label: 'prepare', phase: 'Prepare', schema: PREPARED, model: 'haiku', effort: 'low' },
)
if (!prepared || !prepared.manifest) throw new Error(`prepare_run.py failed: ${prepared && prepared.error}`)
const m = prepared.manifest
const dir = m.run_dir
const qList = m.exam.questions.map(q => `${q.id} (${q.points} pts)`).join(', ')
log(`Run folder ${dir}: ${m.students.length} students. Follow it live: python3 scripts/live_server.py, then http://localhost:8131/run/${dir.replace(/^runs\//, '')}`)

const studentBrief = s => [
  `You are student ${s.sid}. Your persona card: ${s.persona_file}`,
  `Materials you studied (read them before the exam):\n${s.materials.map(p => `- ${p}`).join('\n') || '- none'}`,
  `Exam: "${m.exam.title}", file ${m.exam.student_file}`,
  `Duration: ${m.exam.duration_min} minutes\nAids: ${m.exam.aids || 'as stated on the exam'}\nLanguage: ${m.exam.language || 'as on the exam'}`,
  `Question ids and points: ${qList}`,
  m.exam.typical_score && `Class context: in this course the median student scores about ${Math.round(100 * m.exam.typical_score)}% of the points.`,
  `Write your answer sheet to ${dir}/answers/${s.sid}.json and your feedback to ${dir}/feedback/${s.sid}.json.`,
].filter(Boolean).join('\n\n')

const graderBrief = s => [
  `Grade the answer sheet ${dir}/answers/${s.sid}.json.`,
  `Exam: ${m.exam.student_file}. Solution and rubric: ${m.exam.solution_files.join(', ')}.`,
  `Question ids and maximum points: ${qList}; total ${m.exam.total_points}.`,
  `Write the grades to ${dir}/grades/${s.sid}.json.`,
].join('\n\n')

// No barrier between sitting and grading: each script is graded as soon as it is handed in.
const results = await pipeline(
  m.students,
  s => agent(studentBrief(s), { agentType: 'student', model: s.model, label: `sit:${s.sid}`, phase: 'Sit', schema: SAT }),
  (sat, s) => sat && agent(graderBrief(s), { agentType: 'grader', label: `grade:${s.sid}`, phase: 'Grade', schema: GRADED }),
)
const missing = m.students.filter((s, i) => !results[i]).map(s => s.sid)
if (missing.length) log(`No graded result for ${missing.join(', ')}; they are left out of the statistics.`)
if (missing.length === m.students.length) throw new Error('No student was graded, so there is nothing to analyze.')

// The analysis needs the whole class, so it waits for every script.
phase('Analyze')
const stats = await runScript(`python3 scripts/analyze_run.py ${dir}`, 'stats', 'Analyze')
const feedback = await agent([
  `Run folder: ${dir}`,
  `Exam: ${m.exam.student_file}`,
  `Read ${dir}/feedback/*.json, the ambiguity notes in ${dir}/grades/*.json, and ${dir}/analysis/stats.json.`,
  `Write ${dir}/analysis/feedback.json.`,
].join('\n\n'), { agentType: 'feedback-analyst', label: 'feedback', phase: 'Analyze' })
const review = await agent([
  `Run folder: ${dir}`,
  `Exam: ${m.exam.student_file} (its LaTeX source, if any, is in the same folder). Solution and rubric: ${m.exam.solution_files.join(', ')}.`,
  `Read ${dir}/analysis/stats.json and ${dir}/analysis/feedback.json; consult ${dir}/answers/ and ${dir}/grades/ where you need to check a claim.`,
  `Write ${dir}/analysis/recommendations.json.`,
].join('\n\n'), { agentType: 'exam-reviewer', label: 'review', phase: 'Analyze' })

phase('Report')
await runScript(`python3 scripts/build_dashboard.py ${dir}`, 'dashboard', 'Report')

return { run_dir: dir, dashboard: `${dir}/dashboard.html`, missing, stats, feedback, review }
