import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

/// Condensed display face used for headlines, numbers and timing data.
const racingDisplayFont = 'BarlowCondensed';

const podiumGold = Color(0xFFFFC83D);
const podiumSilver = Color(0xFFC9D1DA);
const podiumBronze = Color(0xFFD9925A);

bool get _isWidgetTest => WidgetsBinding.instance.runtimeType
    .toString()
    .contains('TestWidgetsFlutterBinding');

TextStyle racingDisplay({
  double size = 20,
  FontWeight weight = FontWeight.w800,
  Color? color,
  bool italic = true,
  double letterSpacing = 0,
  double? height,
}) => TextStyle(
  fontFamily: racingDisplayFont,
  fontSize: size,
  fontWeight: weight,
  fontStyle: italic ? FontStyle.italic : FontStyle.normal,
  color: color,
  letterSpacing: letterSpacing,
  height: height,
  fontFeatures: const [FontFeature.tabularFigures()],
);

const _iso3ToIso2 = {
  'ARE': 'ae',
  'AUS': 'au',
  'AUT': 'at',
  'AZE': 'az',
  'BEL': 'be',
  'BRA': 'br',
  'CAN': 'ca',
  'CHN': 'cn',
  'ESP': 'es',
  'FRA': 'fr',
  'GBR': 'gb',
  'HUN': 'hu',
  'ITA': 'it',
  'JPN': 'jp',
  'MCO': 'mc',
  'MEX': 'mx',
  'MYS': 'my',
  'NLD': 'nl',
  'QAT': 'qa',
  'SAU': 'sa',
  'SGP': 'sg',
  'USA': 'us',
};

String? flagAssetForCountry(String? iso3) {
  final code = _iso3ToIso2[iso3?.toUpperCase()];
  return code == null ? null : 'assets/flags/$code.svg';
}

/// Country flag rendered from bundled SVGs so it looks identical on every
/// platform (emoji flags are not available on Windows and many Androids).
class RacingFlag extends StatelessWidget {
  const RacingFlag({
    super.key,
    required this.countryCode,
    this.width = 28,
    this.semanticsLabel,
  });

  final String? countryCode;
  final double width;
  final String? semanticsLabel;

  @override
  Widget build(BuildContext context) {
    final asset = flagAssetForCountry(countryCode);
    final height = width * .72;
    if (asset == null) {
      return SizedBox(
        width: width,
        height: height,
        child: Icon(Icons.sports_score, size: height),
      );
    }
    return Container(
      width: width,
      height: height,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(width / 10),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: .28),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: SvgPicture.asset(
        asset,
        fit: BoxFit.cover,
        semanticsLabel: semanticsLabel,
      ),
    );
  }
}

/// Parallelogram outline: the signature shape of timing screens and kerbs.
class SlantBorder extends OutlinedBorder {
  const SlantBorder({this.slant = 8, super.side});

  final double slant;

  Path _path(Rect rect) => Path()
    ..moveTo(rect.left + slant, rect.top)
    ..lineTo(rect.right, rect.top)
    ..lineTo(rect.right - slant, rect.bottom)
    ..lineTo(rect.left, rect.bottom)
    ..close();

  @override
  EdgeInsetsGeometry get dimensions => EdgeInsets.all(side.width);

  @override
  Path getInnerPath(Rect rect, {TextDirection? textDirection}) =>
      _path(rect.deflate(side.width));

  @override
  Path getOuterPath(Rect rect, {TextDirection? textDirection}) => _path(rect);

  @override
  void paint(Canvas canvas, Rect rect, {TextDirection? textDirection}) {
    if (side.style == BorderStyle.none || side.width == 0) return;
    canvas.drawPath(_path(rect.deflate(side.width / 2)), side.toPaint());
  }

  @override
  ShapeBorder scale(double t) =>
      SlantBorder(slant: slant * t, side: side.scale(t));

  @override
  OutlinedBorder copyWith({BorderSide? side}) =>
      SlantBorder(slant: slant, side: side ?? this.side);
}

class SlantTag extends StatelessWidget {
  const SlantTag({
    super.key,
    required this.label,
    required this.color,
    this.foreground = Colors.white,
    this.fontSize = 12,
  });

  final String label;
  final Color color;
  final Color foreground;
  final double fontSize;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: ShapeDecoration(
      color: color,
      shape: SlantBorder(slant: fontSize * .55),
    ),
    child: Padding(
      padding: EdgeInsets.symmetric(
        horizontal: fontSize * .95,
        vertical: fontSize * .12,
      ),
      child: Text(
        label.toUpperCase(),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: racingDisplay(
          size: fontSize,
          color: foreground,
          letterSpacing: .8,
          height: 1.25,
        ),
      ),
    ),
  );
}

Color? podiumColor(int? position) => switch (position) {
  1 => podiumGold,
  2 => podiumSilver,
  3 => podiumBronze,
  _ => null,
};

/// Timing-tower style position marker with podium colours for P1–P3.
class PositionBadge extends StatelessWidget {
  const PositionBadge({
    super.key,
    required this.label,
    this.position,
    this.width = 40,
  });

  final String label;
  final int? position;
  final double width;

  @override
  Widget build(BuildContext context) {
    final podium = podiumColor(position);
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: width,
      height: 30,
      alignment: Alignment.center,
      decoration: ShapeDecoration(
        color: podium ?? scheme.surfaceContainerHighest,
        shape: const SlantBorder(slant: 7),
        shadows: podium == null
            ? null
            : [BoxShadow(color: podium.withValues(alpha: .35), blurRadius: 10)],
      ),
      child: Text(
        label,
        maxLines: 1,
        style: racingDisplay(
          size: 18,
          color: podium == null ? scheme.onSurface : const Color(0xFF15181D),
        ),
      ),
    );
  }
}

class _CheckerPainter extends CustomPainter {
  const _CheckerPainter({required this.cell, required this.color});
  final double cell;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color;
    final columns = (size.width / cell).ceil();
    final rows = (size.height / cell).ceil();
    for (var row = 0; row < rows; row++) {
      for (var column = 0; column < columns; column++) {
        if ((row + column).isEven) {
          // Fade the flag towards the left so it reads as motion.
          paint.color = color.withValues(
            alpha: color.a * ((column + 1) / columns),
          );
          canvas.drawRect(
            Rect.fromLTWH(column * cell, row * cell, cell, cell),
            paint,
          );
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant _CheckerPainter oldDelegate) =>
      oldDelegate.cell != cell || oldDelegate.color != color;
}

class CheckeredStrip extends StatelessWidget {
  const CheckeredStrip({
    super.key,
    this.width = 60,
    this.height = 18,
    this.cell = 6,
    this.color,
  });

  final double width;
  final double height;
  final double cell;
  final Color? color;

  @override
  Widget build(BuildContext context) => CustomPaint(
    size: Size(width, height),
    painter: _CheckerPainter(
      cell: cell,
      color: color ?? Theme.of(context).colorScheme.onSurface,
    ),
  );
}

/// Pulsing red "LIVE" marker shown while a session is running.
class LiveBadge extends StatefulWidget {
  const LiveBadge({super.key, this.label = 'LIVE'});
  final String label;

  @override
  State<LiveBadge> createState() => _LiveBadgeState();
}

class _LiveBadgeState extends State<LiveBadge>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
    value: 1,
  );

  @override
  void initState() {
    super.initState();
    if (!_isWidgetTest) _pulse.repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: const ShapeDecoration(
      color: Color(0xFFE10600),
      shape: SlantBorder(slant: 6),
    ),
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          FadeTransition(
            opacity: Tween<double>(begin: .25, end: 1).animate(_pulse),
            child: const Icon(Icons.circle, size: 8, color: Colors.white),
          ),
          const SizedBox(width: 5),
          Flexible(
            child: Text(
              widget.label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: racingDisplay(size: 13, color: Colors.white, height: 1.2),
            ),
          ),
        ],
      ),
    ),
  );
}

/// Days / hours / minutes / seconds to [target], ticking every second.
class RaceCountdown extends StatefulWidget {
  const RaceCountdown({
    super.key,
    required this.target,
    required this.units,
    this.color = Colors.white,
  });

  final DateTime target;
  final List<String> units;
  final Color color;

  @override
  State<RaceCountdown> createState() => _RaceCountdownState();
}

class _RaceCountdownState extends State<RaceCountdown> {
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    if (!_isWidgetTest) {
      _ticker = Timer.periodic(
        const Duration(seconds: 1),
        (_) => mounted ? setState(() {}) : null,
      );
    }
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    var left = widget.target.difference(DateTime.now().toUtc());
    if (left.isNegative) left = Duration.zero;
    final values = [
      left.inDays,
      left.inHours % 24,
      left.inMinutes % 60,
      left.inSeconds % 60,
    ];
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var index = 0; index < values.length; index++) ...[
          if (index > 0)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 3),
              child: Text(
                ':',
                style: racingDisplay(
                  size: 24,
                  color: widget.color.withValues(alpha: .45),
                ),
              ),
            ),
          Container(
            width: 52,
            padding: const EdgeInsets.symmetric(vertical: 5),
            decoration: ShapeDecoration(
              color: widget.color.withValues(alpha: .08),
              shape: BeveledRectangleBorder(
                borderRadius: const BorderRadius.only(
                  topRight: Radius.circular(8),
                  bottomLeft: Radius.circular(8),
                ),
                side: BorderSide(color: widget.color.withValues(alpha: .16)),
              ),
            ),
            child: Column(
              children: [
                Text(
                  values[index].toString().padLeft(2, '0'),
                  style: racingDisplay(
                    size: 28,
                    color: widget.color,
                    height: 1,
                    italic: false,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  widget.units[index],
                  style: TextStyle(
                    fontSize: 9,
                    letterSpacing: 1.1,
                    fontWeight: FontWeight.w700,
                    color: widget.color.withValues(alpha: .62),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

/// Bold italic section label followed by a fading racing line.
class RacingSectionHeader extends StatelessWidget {
  const RacingSectionHeader({
    super.key,
    required this.label,
    this.trailing,
    this.color,
  });

  final String label;
  final String? trailing;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final accent = color ?? scheme.primary;
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 10, 2, 10),
      child: Row(
        children: [
          Container(
            width: 14,
            height: 16,
            decoration: ShapeDecoration(
              color: accent,
              shape: const SlantBorder(slant: 5),
            ),
          ),
          const SizedBox(width: 10),
          Flexible(
            flex: 5,
            child: Text(
              label.toUpperCase(),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: racingDisplay(size: 19, letterSpacing: 1),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Container(
              height: 1.5,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [scheme.outline, scheme.outline.withValues(alpha: 0)],
                ),
              ),
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: 10),
            Text(
              trailing!,
              style: TextStyle(
                color: scheme.onSurfaceVariant,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
