export const translations = {
  en: {
    'common.cancel': 'Cancel',
    'common.delete': 'Delete',
    'common.save': 'Save',
    'common.reset': 'Reset',
    'common.remove': 'Remove',
    'common.edit': 'Edit',
    'common.lock': 'Lock',
    'common.loading': 'Loading…',

    'language.switch': 'Switch language',
    'language.en': 'English',
    'language.vi': 'Tiếng Việt',

    'nav.allDatasources': 'All Datasources',
    'nav.knowledgeBase': 'Knowledge Base',
    'nav.skills': 'Skills',
    'nav.pinned': 'Pinned',
    'nav.history': 'History',
    'nav.noPinned': 'No pinned conversations',
    'nav.noHistory': 'No analyses yet',
    'nav.startNewAnalysis': 'Start New Analysis',
    'nav.deleteConversation.title': 'Delete conversation?',
    'nav.deleteConversation.description':
      'This will permanently delete "{{title}}" from your history. This action cannot be undone.',
    'nav.pinConversation': 'Pin conversation',
    'nav.unpinConversation': 'Unpin conversation',
    'nav.deleteConversationAction': 'Delete conversation',

    'sidebar.preparing': 'Preparing...',
    'sidebar.failedToLoad': 'Failed to load.',

    'settings.title': 'API Settings',
    'settings.aria': 'Settings',
    'settings.baseUrl': 'Base URL',
    'settings.apiKey': 'API Key',
    'settings.embedUrl': 'Embedding Base URL',
    'settings.embedModel': 'Embedding Model',
    'settings.embedHint':
      'Used for knowledge-base ingestion + retrieval. Changing the model after documents are uploaded invalidates existing vectors — re-upload to re-index.',

    'theme.toggle': 'Toggle theme',
    'theme.light': 'Light',
    'theme.dark': 'Dark',
    'theme.system': 'System',

    'agents.title': 'Assistant',
    'agents.subtitle':
      'The center stages focused on chat, streaming analysis, and quick actions.',
    'agents.heroSubtitle':
      'Ask a business question and let multiple AI agents collaborate to analyze your data.',
    'agents.connectTableFirst': 'Connect at least one table first.',
    'agents.failedStartRun': 'Failed to start run',
    'agents.failedStartAnalysis': 'Failed to start analysis',
    'agents.failedApproval': 'Failed to send approval',
    'agents.failedRejection': 'Failed to send rejection',

    'composer.placeholder':
      'Describe your analysis task — use @ for knowledge base, / for skills',
    'composer.selectModel': 'Select a model',
    'composer.selectTables': 'Select tables',
    'composer.knowledgeBase': 'knowledge base',
    'composer.searchDocuments': 'Search documents…',
    'composer.skill': 'skill',
    'composer.searchSkills': 'Search skills…',

    'datasources.title': 'Datasources',
    'datasources.new': 'New Datasource',
    'datasources.add': 'Add Datasource',
    'datasources.loading': 'Loading datasources...',
    'datasources.failed': 'Failed to load datasources.',
    'datasources.empty': 'No datasources connected yet.',
    'datasources.removeTitle': 'Remove datasource?',
    'datasources.removeDescription':
      '{{name}} ({{type}}) will be deregistered. This action cannot be undone.',
    'datasources.removeAction': 'Remove datasource',

    'kb.title': 'Knowledge Base',
    'kb.subtitle': 'Upload documents your agent can reference during analysis.',
    'kb.supported': 'Supported:',
    'kb.uploading': 'Uploading…',
    'kb.dropHere': 'Drop files here',
    'kb.dragDrop': 'Drag & drop files here, or click to browse',
    'kb.uploadedDocs': 'Uploaded Documents',
    'kb.empty': 'No documents uploaded yet.',
    'kb.deleteDoc': 'Delete document',
    'kb.uploadSuccess': '{{filename}} — {{chunks}} chunks stored',
    'kb.uploadFailed': 'Upload failed',

    'skills.title': 'Skills & Templates',
    'skills.subtitle':
      'Add SQL templates, chart recipes, or pipeline patterns your agent can reuse.',
    'skills.addNew': 'Add new skill',
    'skills.editSkill': 'Edit skill',
    'skills.name': 'Name',
    'skills.description': 'Description (used for semantic search)',
    'skills.type': 'Type',
    'skills.template': 'Template / code',
    'skills.saveChanges': 'Save changes',
    'skills.addSkill': 'Add skill',
    'skills.allSkills': 'All Skills',
    'skills.builtin': '(built-in)',
    'skills.nameRequired': 'Name is required',
    'skills.updated': 'Skill updated',
    'skills.added': 'Skill added',
    'skills.saveFailed': 'Failed to save skill',
    'skills.sqlTemplate': 'SQL template',
    'skills.chartRecipe': 'Chart recipe',
    'skills.pipelinePattern': 'Pipeline pattern',

    'approval.humanReview': 'Human Review Required',
    'approval.sql.title': 'SQL Query Generated',
    'approval.sql.description':
      'Review the generated SQL before it is executed against your database.',
    'approval.sql.rejectLabel':
      'Reason for rejection or edit SQL (required — helps the agent regenerate):',
    'approval.sql.rejectPlaceholder':
      'e.g. "Missing filter for current month", "Wrong table used"…',
    'approval.sql.rejectRegenerate': 'Reject & Regenerate',
    'approval.sql.approveEdited': 'Approve Edited SQL',
    'approval.sql.approveExecute': 'Approve & Execute',
    'approval.sql.sendRejection': 'Send Rejection',

    'approval.python.title': 'Python Code Generated',
    'approval.python.description':
      'Review the generated Python before it runs in the sandbox.',
    'approval.python.risk': '{{risk}} risk',
    'approval.python.rejectLabel':
      'Reason for rejection or edit the code (required — helps the agent regenerate):',
    'approval.python.rejectPlaceholder':
      'e.g. "Avoid network calls", "Use df_result instead"…',
    'approval.python.approveEdited': 'Approve Edited Code',
    'approval.python.approveExecute': 'Approve & Execute',

    'approval.web.title': 'Import data from the web?',
    'approval.web.description':
      'The agent found public dataset sources because existing datasources do not cover this question. Approve only the URLs you trust before they are added to your workspace.',
    'approval.web.searchNeed': 'Search need:',
    'approval.web.proposedUrls': 'Proposed dataset URLs',
    'approval.web.noUrls': 'No URLs were proposed.',
    'approval.web.rejectLabel':
      'Reason for declining (helps the agent choose another path):',
    'approval.web.rejectPlaceholder':
      'e.g. "Use only internal HR data", "Wrong geography"',
    'approval.web.decline': 'Decline import',
    'approval.web.approveImport': 'Approve & import ({{count}})',
    'approval.web.confirmDecline': 'Confirm decline',

    'toast.conversationDeleted': 'Conversation deleted',
    'toast.couldNotDeleteConversation': 'Could not delete conversation on server',
    'toast.sessionUnavailable': 'This session is no longer available.',
    'toast.codeCopied': 'Code copied to clipboard',
    'toast.copyFailed': 'Failed to copy to clipboard',

    'presets.noTables':
      'No tables found for "{{label}}". Register sample data from sample_dataset first.',
    'presets.expected': 'Expected: {{description}}',
    'presets.failedLoadPreset': 'Failed to load preset prompt for "{{label}}".',
    'presets.failedLoadLite': 'Failed to load lite test prompt.',
  },
  vi: {
    'common.cancel': 'Hủy',
    'common.delete': 'Xóa',
    'common.save': 'Lưu',
    'common.reset': 'Đặt lại',
    'common.remove': 'Gỡ bỏ',
    'common.edit': 'Chỉnh sửa',
    'common.lock': 'Khóa',
    'common.loading': 'Đang tải…',

    'language.switch': 'Đổi ngôn ngữ',
    'language.en': 'English',
    'language.vi': 'Tiếng Việt',

    'nav.allDatasources': 'Tất cả nguồn dữ liệu',
    'nav.knowledgeBase': 'Cơ sở tri thức',
    'nav.skills': 'Kỹ năng',
    'nav.pinned': 'Đã ghim',
    'nav.history': 'Lịch sử',
    'nav.noPinned': 'Chưa có cuộc trò chuyện được ghim',
    'nav.noHistory': 'Chưa có phân tích nào',
    'nav.startNewAnalysis': 'Bắt đầu phân tích mới',
    'nav.deleteConversation.title': 'Xóa cuộc trò chuyện?',
    'nav.deleteConversation.description':
      'Thao tác này sẽ xóa vĩnh viễn "{{title}}" khỏi lịch sử. Không thể hoàn tác.',
    'nav.pinConversation': 'Ghim cuộc trò chuyện',
    'nav.unpinConversation': 'Bỏ ghim cuộc trò chuyện',
    'nav.deleteConversationAction': 'Xóa cuộc trò chuyện',

    'sidebar.preparing': 'Đang chuẩn bị...',
    'sidebar.failedToLoad': 'Không tải được.',

    'settings.title': 'Cài đặt API',
    'settings.aria': 'Cài đặt',
    'settings.baseUrl': 'URL cơ sở',
    'settings.apiKey': 'Khóa API',
    'settings.embedUrl': 'URL nhúng (Embedding)',
    'settings.embedModel': 'Mô hình nhúng',
    'settings.embedHint':
      'Dùng cho nhập và truy xuất cơ sở tri thức. Đổi mô hình sau khi tải tài liệu sẽ vô hiệu vector hiện có — tải lại để lập chỉ mục.',

    'theme.toggle': 'Đổi giao diện',
    'theme.light': 'Sáng',
    'theme.dark': 'Tối',
    'theme.system': 'Hệ thống',

    'agents.title': 'Trợ lý',
    'agents.subtitle':
      'Trung tâm tập trung vào trò chuyện, phân tích theo luồng và thao tác nhanh.',
    'agents.heroSubtitle':
      'Đặt câu hỏi kinh doanh và để nhiều tác nhân AI cùng phân tích dữ liệu của bạn.',
    'agents.connectTableFirst': 'Hãy kết nối ít nhất một bảng trước.',
    'agents.failedStartRun': 'Không thể bắt đầu phiên chạy',
    'agents.failedStartAnalysis': 'Không thể bắt đầu phân tích',
    'agents.failedApproval': 'Không thể gửi phê duyệt',
    'agents.failedRejection': 'Không thể gửi từ chối',

    'composer.placeholder':
      'Mô tả tác vụ phân tích — dùng @ cho cơ sở tri thức, / cho kỹ năng',
    'composer.selectModel': 'Chọn mô hình',
    'composer.selectTables': 'Chọn bảng',
    'composer.knowledgeBase': 'cơ sở tri thức',
    'composer.searchDocuments': 'Tìm tài liệu…',
    'composer.skill': 'kỹ năng',
    'composer.searchSkills': 'Tìm kỹ năng…',

    'datasources.title': 'Nguồn dữ liệu',
    'datasources.new': 'Nguồn dữ liệu mới',
    'datasources.add': 'Thêm nguồn dữ liệu',
    'datasources.loading': 'Đang tải nguồn dữ liệu...',
    'datasources.failed': 'Không tải được nguồn dữ liệu.',
    'datasources.empty': 'Chưa có nguồn dữ liệu nào được kết nối.',
    'datasources.removeTitle': 'Gỡ nguồn dữ liệu?',
    'datasources.removeDescription':
      '{{name}} ({{type}}) sẽ bị hủy đăng ký. Không thể hoàn tác.',
    'datasources.removeAction': 'Gỡ nguồn dữ liệu',

    'kb.title': 'Cơ sở tri thức',
    'kb.subtitle': 'Tải tài liệu để tác nhân tham chiếu khi phân tích.',
    'kb.supported': 'Hỗ trợ:',
    'kb.uploading': 'Đang tải lên…',
    'kb.dropHere': 'Thả tệp vào đây',
    'kb.dragDrop': 'Kéo thả tệp vào đây, hoặc nhấp để duyệt',
    'kb.uploadedDocs': 'Tài liệu đã tải lên',
    'kb.empty': 'Chưa có tài liệu nào.',
    'kb.deleteDoc': 'Xóa tài liệu',
    'kb.uploadSuccess': '{{filename}} — đã lưu {{chunks}} đoạn',
    'kb.uploadFailed': 'Tải lên thất bại',

    'skills.title': 'Kỹ năng & Mẫu',
    'skills.subtitle':
      'Thêm mẫu SQL, công thức biểu đồ hoặc quy trình để tác nhân tái sử dụng.',
    'skills.addNew': 'Thêm kỹ năng mới',
    'skills.editSkill': 'Sửa kỹ năng',
    'skills.name': 'Tên',
    'skills.description': 'Mô tả (dùng cho tìm kiếm ngữ nghĩa)',
    'skills.type': 'Loại',
    'skills.template': 'Mẫu / mã',
    'skills.saveChanges': 'Lưu thay đổi',
    'skills.addSkill': 'Thêm kỹ năng',
    'skills.allSkills': 'Tất cả kỹ năng',
    'skills.builtin': '(tích hợp sẵn)',
    'skills.nameRequired': 'Tên là bắt buộc',
    'skills.updated': 'Đã cập nhật kỹ năng',
    'skills.added': 'Đã thêm kỹ năng',
    'skills.saveFailed': 'Không lưu được kỹ năng',
    'skills.sqlTemplate': 'Mẫu SQL',
    'skills.chartRecipe': 'Công thức biểu đồ',
    'skills.pipelinePattern': 'Mẫu quy trình',

    'approval.humanReview': 'Cần người xem xét',
    'approval.sql.title': 'Đã tạo truy vấn SQL',
    'approval.sql.description':
      'Xem lại SQL đã tạo trước khi thực thi trên cơ sở dữ liệu.',
    'approval.sql.rejectLabel':
      'Lý do từ chối hoặc chỉnh sửa SQL (bắt buộc — giúp tác nhân tạo lại):',
    'approval.sql.rejectPlaceholder':
      'vd. "Thiếu bộ lọc tháng hiện tại", "Dùng sai bảng"…',
    'approval.sql.rejectRegenerate': 'Từ chối & Tạo lại',
    'approval.sql.approveEdited': 'Phê duyệt SQL đã sửa',
    'approval.sql.approveExecute': 'Phê duyệt & Thực thi',
    'approval.sql.sendRejection': 'Gửi từ chối',

    'approval.python.title': 'Đã tạo mã Python',
    'approval.python.description':
      'Xem lại mã Python trước khi chạy trong sandbox.',
    'approval.python.risk': 'Rủi ro {{risk}}',
    'approval.python.rejectLabel':
      'Lý do từ chối hoặc chỉnh sửa mã (bắt buộc — giúp tác nhân tạo lại):',
    'approval.python.rejectPlaceholder':
      'vd. "Tránh gọi mạng", "Dùng df_result thay thế"…',
    'approval.python.approveEdited': 'Phê duyệt mã đã sửa',
    'approval.python.approveExecute': 'Phê duyệt & Thực thi',

    'approval.web.title': 'Nhập dữ liệu từ web?',
    'approval.web.description':
      'Tác nhân tìm thấy nguồn dữ liệu công khai vì nguồn hiện có chưa đủ. Chỉ phê duyệt URL bạn tin cậy trước khi thêm vào không gian làm việc.',
    'approval.web.searchNeed': 'Nhu cầu tìm kiếm:',
    'approval.web.proposedUrls': 'URL bộ dữ liệu đề xuất',
    'approval.web.noUrls': 'Không có URL nào được đề xuất.',
    'approval.web.rejectLabel':
      'Lý do từ chối (giúp tác nhân chọn hướng khác):',
    'approval.web.rejectPlaceholder':
      'vd. "Chỉ dùng dữ liệu HR nội bộ", "Sai khu vực địa lý"',
    'approval.web.decline': 'Từ chối nhập',
    'approval.web.approveImport': 'Phê duyệt & nhập ({{count}})',
    'approval.web.confirmDecline': 'Xác nhận từ chối',

    'toast.conversationDeleted': 'Đã xóa cuộc trò chuyện',
    'toast.couldNotDeleteConversation': 'Không xóa được cuộc trò chuyện trên máy chủ',
    'toast.sessionUnavailable': 'Phiên này không còn khả dụng.',
    'toast.codeCopied': 'Đã sao chép mã',
    'toast.copyFailed': 'Không sao chép được',

    'presets.noTables':
      'Không tìm thấy bảng cho "{{label}}". Hãy đăng ký dữ liệu mẫu từ sample_dataset trước.',
    'presets.expected': 'Cần có: {{description}}',
    'presets.failedLoadPreset': 'Không tải được prompt mẫu cho "{{label}}".',
    'presets.failedLoadLite': 'Không tải được prompt kiểm thử lite.',
  },
} as const

export type Locale = keyof typeof translations
export type TranslationKey = keyof (typeof translations)['en']
