import _pt from "prop-types";
var _excluded = ["className", "children", "debounceTime", "ignoreDimensions", "initialSize", "parentSizeStyles", "enableDebounceLeadingCall", "resizeObserverPolyfill"],
  _excluded2 = ["parentRef", "resize"];
function _extends() { _extends = Object.assign ? Object.assign.bind() : function (target) { for (var i = 1; i < arguments.length; i++) { var source = arguments[i]; for (var key in source) { if (Object.prototype.hasOwnProperty.call(source, key)) { target[key] = source[key]; } } } return target; }; return _extends.apply(this, arguments); }
function _objectWithoutPropertiesLoose(source, excluded) { if (source == null) return {}; var target = {}; var sourceKeys = Object.keys(source); var key, i; for (i = 0; i < sourceKeys.length; i++) { key = sourceKeys[i]; if (excluded.indexOf(key) >= 0) continue; target[key] = source[key]; } return target; }
import React from 'react';
import useParentSize from '../hooks/useParentSize';
var defaultParentSizeStyles = {
  width: '100%',
  height: '100%'
};
export default function ParentSize(_ref) {
  var className = _ref.className,
    children = _ref.children,
    debounceTime = _ref.debounceTime,
    ignoreDimensions = _ref.ignoreDimensions,
    initialSize = _ref.initialSize,
    _ref$parentSizeStyles = _ref.parentSizeStyles,
    parentSizeStyles = _ref$parentSizeStyles === void 0 ? defaultParentSizeStyles : _ref$parentSizeStyles,
    _ref$enableDebounceLe = _ref.enableDebounceLeadingCall,
    enableDebounceLeadingCall = _ref$enableDebounceLe === void 0 ? true : _ref$enableDebounceLe,
    resizeObserverPolyfill = _ref.resizeObserverPolyfill,
    restProps = _objectWithoutPropertiesLoose(_ref, _excluded);
  var _useParentSize = useParentSize({
      initialSize: initialSize,
      debounceTime: debounceTime,
      ignoreDimensions: ignoreDimensions,
      enableDebounceLeadingCall: enableDebounceLeadingCall,
      resizeObserverPolyfill: resizeObserverPolyfill
    }),
    parentRef = _useParentSize.parentRef,
    resize = _useParentSize.resize,
    dimensions = _objectWithoutPropertiesLoose(_useParentSize, _excluded2);
  return /*#__PURE__*/React.createElement("div", _extends({
    style: parentSizeStyles,
    ref: parentRef,
    className: className
  }, restProps), children(_extends({}, dimensions, {
    ref: parentRef.current,
    resize: resize
  })));
}
ParentSize.propTypes = {
  className: _pt.string,
  children: _pt.func.isRequired
};