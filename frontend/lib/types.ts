export interface User {
  public_id: string
  email: string
  first_name: string
  last_name: string
  phone: string | null
  position: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  roles: string[]
}

export interface Product {
  public_id: string
  sku: string
  name: string
  type: 'KIT' | 'COMPONENT'
  description: string | null
  qr_code: string | null
  is_active: boolean
  cut_file_key: string | null
  cut_file_notes: string | null
  created_at: string
  updated_at: string
}

export interface KitBomItem {
  component_public_id: string
  component_sku: string
  component_name: string
  quantity: number
  notes: string | null
  created_at: string
}

export interface LocationRead {
  public_id: string
  name: string
  type: string
  address: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface OrderItem {
  id: number
  product_id: number
  quantity: number
  unit_price: string
  snapshot_name: string | null
  snapshot_sku: string | null
}

export interface SalesOrder {
  public_id: string
  external_id: string | null
  source: string
  status: string
  fulfillment_status: string
  customer_name: string
  customer_email: string
  customer_phone: string | null
  shipping_address: string | null
  billing_address: string | null
  notes: string | null
  qr_token: string | null
  created_by_name: string | null
  approved_at: string | null
  snapshot_frozen_at: string | null
  created_at: string
  updated_at: string
  items: OrderItem[]
}

export interface StockLocation {
  public_id: string
  name: string
  type: string
}

export interface InventorySummaryItem {
  product_id: number
  status: string
  total_quantity: number
}

export interface ProductionBlock {
  id: number
  component_id: number
  missing_qty: number
  resolved_at: string | null
}

export interface BatchItemRead {
  batch_item_id: number
  product_id: number
  product_sku: string
  product_name: string
  required_qty_total: number
  available_stock_qty: number
  to_produce_qty: number
  produced_qty: number
  blocks: ProductionBlock[]
}

export interface LinkedOrderRead {
  sales_order_id: number
  link_mode: string
}

export interface ProductionBatch {
  public_id: string
  kind: string
  status: string
  name: string | null
  notes: string | null
  cutoff_at: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  items: BatchItemRead[]
  linked_orders: LinkedOrderRead[]
}

export interface BomComponentDetail {
  component_id: number
  component_sku: string
  component_name: string
  qty_per_kit: number
  total_needed: number
  available: number
  missing: number
}

export interface MasterSheetItem {
  batch_item_id: number
  product_id: number
  product_sku: string
  product_name: string
  required_qty_total: number
  available_stock_qty: number
  to_produce_qty: number
  produced_qty: number
  bom: BomComponentDetail[]
  blocks: ProductionBlock[]
}

export interface MasterSheetResponse {
  batch_public_id: string
  kind: string
  status: string
  name: string | null
  cutoff_at: string | null
  items: MasterSheetItem[]
  linked_orders: LinkedOrderRead[]
}

export interface PackItem {
  id: number
  public_id: string
  sales_order_id: number
  product_id: number
  required_qty: number
  confirmed_qty: number
}

export interface PackEvent {
  id: number
  event_type: string
  quantity: number | null
  scanned_qr: string | null
  notes: string | null
  created_at: string
}

export interface PackStatusResponse {
  order_public_id: string
  fulfillment_status: string
  items: PackItem[]
  events: PackEvent[]
}

export interface Role {
  public_id: string
  name: string
  description: string | null
  permission_count: number
  created_at: string
  updated_at: string
}

export interface Permission {
  public_id: string
  code: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface StockAlert {
  product_id: number
  product_name: string
  sku: string
  total_free: number
  status_color: 'RED' | 'YELLOW' | 'GREEN'
}

export interface ApiError {
  status: number
  detail: string
}

// ── Academic ─────────────────────────────────────────────────────────────────

export type WorkLine = 'kuntur' | 'ecua' | 'robotschool'

export interface School {
  public_id: string
  name: string
  city: string | null
  address: string | null
  contact_name: string | null
  contact_email: string | null
  contact_phone: string | null
  work_line: WorkLine | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Grade {
  public_id: string
  name: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface GradeWithCourses extends Grade {
  school_public_id: string | null
  courses: CourseRead[]
  director: User | null
}

export interface CourseRead {
  public_id: string
  name: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MyCourseRead {
  public_id: string
  name: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  grade_name: string
  school_name: string
  teacher_name: string
  role: 'TEACHER' | 'STUDENT'
}

export interface CourseDetail {
  public_id: string
  name: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  teacher: User
  students: User[]
  units: UnitRead[]
}

export interface GradebookAssignment {
  public_id: string
  title: string
  max_score: number
  due_date: string | null
}

export interface GradebookGrade {
  score: number | null
  status: string
  submission_public_id: string
}

export interface GradebookStudent {
  student: { public_id: string; first_name: string; last_name: string; email: string }
  grades: Record<string, GradebookGrade | null>
  average: number | null
  completed: number
  total: number
}

export interface Gradebook {
  course: { public_id: string; name: string }
  assignments: GradebookAssignment[]
  students: GradebookStudent[]
}

export interface UnitRead {
  public_id: string
  title: string
  description: string | null
  order_index: number
  is_published: boolean
  created_at: string
  updated_at: string
}

export interface MaterialRead {
  public_id: string
  title: string
  type: string
  content: string | null
  file_key: string | null
  has_file: boolean
  file_name: string | null
  order_index: number
  is_published: boolean
  created_at: string
  updated_at: string
}

export interface AssignmentRead {
  public_id: string
  title: string
  description: string | null
  due_date: string | null
  max_score: number
  is_published: boolean
  created_at: string
  updated_at: string
}

export interface SubmissionWithStudent {
  public_id: string
  content: string | null
  file_name: string | null
  status: string
  score: number | null
  feedback: string | null
  submitted_at: string | null
  graded_at: string | null
  created_at: string
  updated_at: string
  student: User
}

export interface MySubmission {
  public_id: string
  content: string | null
  file_key: string | null
  file_name: string | null
  status: string
  score: number | null
  feedback: string | null
  submitted_at: string | null
  graded_at: string | null
  created_at: string
  updated_at: string
}

export interface StudentAssignment {
  public_id: string
  title: string
  description: string | null
  due_date: string | null
  max_score: number
  is_published: boolean
  my_submission: MySubmission | null
}

export interface StudentUnitContent {
  public_id: string
  title: string
  description: string | null
  order_index: number
  is_published: boolean
  materials: MaterialRead[]
  assignments: StudentAssignment[]
}

// ── Training ────────────────────────────────────────────────────────────────

export interface TrainingProgram {
  public_id: string
  name: string
  description: string | null
  objective: string | null
  duration_hours: number | null
  is_active: boolean
  is_published: boolean
  created_at: string
  updated_at: string
}

export interface TeacherProgramProgress {
  program_id: string
  program_name: string
  total_lessons: number
  completed_lessons: number
  total_evaluations: number
  passed_evaluations: number
  overall_score: number | null
  is_certified: boolean
  certificate_code: string | null
}

export interface TrainingEnrollmentProgress {
  user: { public_id: string; first_name: string; last_name: string; email: string }
  enrollment_public_id: string
  status: string
  lessons_completed: number
  lessons_total: number
  evaluations_passed: number
  evaluations_total: number
  average_score: number
  is_eligible: boolean
}
