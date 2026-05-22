import 'package:flutter/material.dart';

/// Founder / platform operator shell: KYC pipeline & global revenue (placeholder).
class SaasSuperAdminView extends StatelessWidget {
  const SaasSuperAdminView({super.key, required this.onSignOut});

  final Future<void> Function() onSignOut;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('OmniPOS — SaaS console'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => onSignOut(),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Super admin',
            style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          Text(
            'KYC applications, tenant provisioning, and cross-store metrics will appear here.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 24),
          _PlaceholderCard(
            icon: Icons.verified_user_outlined,
            title: 'KYC applications',
            subtitle: 'Pending / approved merchant onboarding queue.',
          ),
          const SizedBox(height: 12),
          _PlaceholderCard(
            icon: Icons.payments_outlined,
            title: 'Global revenue',
            subtitle: 'SaaS billing rails — MRR, settlements, and arrears (read-only).',
          ),
        ],
      ),
    );
  }
}

class _PlaceholderCard extends StatelessWidget {
  const _PlaceholderCard({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: ListTile(
        leading: Icon(icon, color: theme.colorScheme.primary),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
  }
}
