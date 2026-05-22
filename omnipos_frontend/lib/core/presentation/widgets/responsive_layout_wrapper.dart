import 'package:flutter/material.dart';

/// Caps content width on large screens so forms and POS panels do not stretch
/// edge-to-edge on web/desktop.
class ResponsiveLayoutWrapper extends StatelessWidget {
  const ResponsiveLayoutWrapper({
    super.key,
    required this.child,
    this.maxWidth = 460,
    this.padding = const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
    this.alignment = Alignment.center,
  });

  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry padding;
  final AlignmentGeometry alignment;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: alignment,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: Padding(
          padding: padding,
          child: child,
        ),
      ),
    );
  }
}
