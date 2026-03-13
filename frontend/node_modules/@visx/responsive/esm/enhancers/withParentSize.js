function _extends() { _extends = Object.assign ? Object.assign.bind() : function (target) { for (var i = 1; i < arguments.length; i++) { var source = arguments[i]; for (var key in source) { if (Object.prototype.hasOwnProperty.call(source, key)) { target[key] = source[key]; } } } return target; }; return _extends.apply(this, arguments); }
function _inheritsLoose(subClass, superClass) { subClass.prototype = Object.create(superClass.prototype); subClass.prototype.constructor = subClass; _setPrototypeOf(subClass, superClass); }
function _setPrototypeOf(o, p) { _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) { o.__proto__ = p; return o; }; return _setPrototypeOf(o, p); }
import debounce from 'lodash/debounce';
import React from 'react';
var CONTAINER_STYLES = {
  width: '100%',
  height: '100%'
};

/**
 * @deprecated
 * @TODO remove in the next major version - exported for backwards compatibility
 */

export default function withParentSize(BaseComponent, /** Optionally inject a ResizeObserver polyfill, else this *must* be globally available. */
resizeObserverPolyfill) {
  return /*#__PURE__*/function (_React$Component) {
    _inheritsLoose(WrappedComponent, _React$Component);
    function WrappedComponent() {
      var _ref, _BaseComponent$displa, _this$props$debounceT, _this$props$enableDeb;
      var _this;
      for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
        args[_key] = arguments[_key];
      }
      _this = _React$Component.call.apply(_React$Component, [this].concat(args)) || this;
      _this.displayName = "withParentSize(" + ((_ref = (_BaseComponent$displa = BaseComponent.displayName) != null ? _BaseComponent$displa : BaseComponent.name) != null ? _ref : 'Component') + ")";
      _this.state = {
        parentWidth: undefined,
        parentHeight: undefined
      };
      _this.animationFrameID = 0;
      _this.container = null;
      _this.setRef = function (ref) {
        _this.container = ref;
      };
      _this.resize = debounce(
      // eslint-disable-next-line unicorn/consistent-function-scoping
      function (_ref2) {
        var width = _ref2.width,
          height = _ref2.height;
        _this.setState({
          parentWidth: width,
          parentHeight: height
        });
      }, (_this$props$debounceT = _this.props.debounceTime) != null ? _this$props$debounceT : 300, {
        leading: (_this$props$enableDeb = _this.props.enableDebounceLeadingCall) != null ? _this$props$enableDeb : true
      });
      return _this;
    }
    var _proto = WrappedComponent.prototype;
    _proto.componentDidMount = function componentDidMount() {
      var _this2 = this;
      var ResizeObserverLocal = resizeObserverPolyfill || window.ResizeObserver;
      this.resizeObserver = new ResizeObserverLocal(function (entries) {
        entries.forEach(function (entry) {
          var _entry$contentRect = entry.contentRect,
            width = _entry$contentRect.width,
            height = _entry$contentRect.height;
          _this2.animationFrameID = window.requestAnimationFrame(function () {
            _this2.resize({
              width: width,
              height: height
            });
          });
        });
      });
      if (this.container) this.resizeObserver.observe(this.container);
    };
    _proto.componentWillUnmount = function componentWillUnmount() {
      window.cancelAnimationFrame(this.animationFrameID);
      if (this.resizeObserver) this.resizeObserver.disconnect();
      this.resize.cancel();
    };
    _proto.render = function render() {
      var _this$props = this.props,
        initialWidth = _this$props.initialWidth,
        initialHeight = _this$props.initialHeight;
      var _this$state = this.state,
        _this$state$parentWid = _this$state.parentWidth,
        parentWidth = _this$state$parentWid === void 0 ? initialWidth : _this$state$parentWid,
        _this$state$parentHei = _this$state.parentHeight,
        parentHeight = _this$state$parentHei === void 0 ? initialHeight : _this$state$parentHei;
      return /*#__PURE__*/React.createElement("div", {
        style: CONTAINER_STYLES,
        ref: this.setRef
      }, parentWidth != null && parentHeight != null && /*#__PURE__*/React.createElement(BaseComponent, _extends({
        parentWidth: parentWidth,
        parentHeight: parentHeight
      }, this.props)));
    };
    return WrappedComponent;
  }(React.Component);
}