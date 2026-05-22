/// Mirrors `GET /api/accounts/user/profile/` (OmniPOS backend).
class UserProfileModel {
  const UserProfileModel({
    required this.userId,
    required this.username,
    required this.email,
    required this.isStaff,
    required this.isSuperuser,
    required this.roles,
    required this.permissions,
    this.assignedBranchName,
  });

  final String userId;
  final String username;
  final String email;
  final bool isStaff;
  final bool isSuperuser;
  /// Role slugs from ``staff_profile.role.name`` (tenant RBAC).
  final List<String> roles;
  /// Flattened Django permission keys (``app_label.codename``).
  final List<String> permissions;

  /// Preferred branch label when present; falls back to primary branch code from API.
  final String? assignedBranchName;

  factory UserProfileModel.fromJson(Map<String, dynamic> json) {
    final staff = json['staff_profile'];
    var roles = <String>[];
    String? branchLabel;
    if (staff is Map<String, dynamic>) {
      final roleMap = staff['role'];
      if (roleMap is Map<String, dynamic>) {
        final name = roleMap['name'] as String?;
        if (name != null && name.isNotEmpty) {
          roles = [name];
        }
      }
      branchLabel = staff['primary_branch_name'] as String? ??
          (staff['primary_branch_code'] as String?)?.trim();
      if (branchLabel != null && branchLabel.isEmpty) {
        branchLabel = null;
      }
    }

    final permsRaw = json['permissions'];
    final permissions = <String>[];
    if (permsRaw is List<dynamic>) {
      for (final p in permsRaw) {
        if (p is String) {
          permissions.add(p);
        }
      }
    }

    return UserProfileModel(
      userId: json['user_id'] as String? ?? '',
      username: json['username'] as String? ?? '',
      email: json['email'] as String? ?? '',
      isStaff: json['is_staff'] as bool? ?? false,
      isSuperuser: json['is_superuser'] as bool? ?? false,
      roles: roles,
      permissions: permissions,
      assignedBranchName: branchLabel,
    );
  }
}
