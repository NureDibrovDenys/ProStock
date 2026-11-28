import 'package:flutter/material.dart';

import '../../core/theme.dart';
import '../auth/auth_controller.dart';

/// Тимчасовий головний екран після входу. Сюди додаватимуться завдання комірника.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key, required this.auth});

  final AuthController auth;

  @override
  Widget build(BuildContext context) {
    final user = auth.user!;

    return Scaffold(
      appBar: AppBar(
        title: const Text('ProStock'),
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.onPrimary,
        actions: [
          IconButton(
            tooltip: 'Вийти',
            icon: const Icon(Icons.logout),
            onPressed: auth.logout,
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Вітаємо, ${user.firstName}!',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text(user.email, style: const TextStyle(color: AppColors.muted)),
            if (user.warehouseId != null)
              Text(
                'Склад №${user.warehouseId}',
                style: const TextStyle(color: AppColors.muted),
              ),
          ],
        ),
      ),
    );
  }
}
