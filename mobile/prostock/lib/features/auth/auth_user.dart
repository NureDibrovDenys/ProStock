/// Користувач, який увійшов у систему (поле `user` з відповіді `/auth/login`).
class AuthUser {
  const AuthUser({
    required this.id,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.role,
    required this.status,
    required this.warehouseId,
    required this.permissions,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) => AuthUser(
        id: json['user_id'] as int,
        email: json['user_email'] as String,
        firstName: json['first_name'] as String,
        lastName: json['last_name'] as String,
        role: json['role'] as String,
        status: json['status'] as String,
        warehouseId: json['warehouse_id'] as int?,
        permissions: (json['permissions'] as Map<String, dynamic>? ?? {})
            .map((key, value) => MapEntry(key, value == true)),
      );

  final int id;
  final String email;
  final String firstName;
  final String lastName;
  final String role;
  final String status;
  final int? warehouseId;
  final Map<String, bool> permissions;

  String get fullName => '$firstName $lastName'.trim();

  bool can(String permission) => permissions[permission] ?? false;
}
