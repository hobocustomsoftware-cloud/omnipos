import 'package:flutter/material.dart';

/// Counter / catalog shell: product grid uses max cross-axis extent so tiles stay
/// readable on wide desktop without stretching a single row across the screen.
///
/// Named route: [routeName] (`/pos-counter`).
class PosCounterView extends StatelessWidget {
  const PosCounterView({super.key, this.onSignOut});

  /// Optional sign-out (wired from authenticated session shell).
  final Future<void> Function()? onSignOut;

  static const String routeName = '/pos-counter';
  static const double _tileExtent = 180;

  @override
  Widget build(BuildContext context) {
    const placeholderCount = 18;

    return Scaffold(
      appBar: AppBar(
        title: const Text('POS'),
        actions: [
          IconButton(
            tooltip: 'Search / scanner',
            icon: const Icon(Icons.search),
            onPressed: () {},
          ),
          if (onSignOut != null)
            IconButton(
              tooltip: 'Sign out',
              icon: const Icon(Icons.logout),
              onPressed: () => onSignOut!(),
            ),
        ],
      ),
      body: CustomScrollView(
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
            sliver: SliverToBoxAdapter(
              child: Text(
                'Products',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.all(8),
            sliver: SliverGrid(
              gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: _tileExtent,
                mainAxisSpacing: 8,
                crossAxisSpacing: 8,
                childAspectRatio: 0.85,
              ),
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  return Card(
                    clipBehavior: Clip.antiAlias,
                    child: InkWell(
                      onTap: () {},
                      child: Padding(
                        padding: const EdgeInsets.all(8),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Expanded(
                              child: Container(
                                decoration: BoxDecoration(
                                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                alignment: Alignment.center,
                                child: Icon(
                                  Icons.inventory_2_outlined,
                                  size: 36,
                                  color: Theme.of(context).colorScheme.outline,
                                ),
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'SKU ${index + 1}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.labelMedium,
                            ),
                            Text(
                              '0.00',
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
                childCount: placeholderCount,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
