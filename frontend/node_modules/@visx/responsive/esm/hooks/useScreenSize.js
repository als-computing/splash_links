import debounce from 'lodash/debounce';
import { useEffect, useMemo, useState } from 'react';
var defaultInitialSize = {
  width: 0,
  height: 0
};
var useScreenSize = function useScreenSize(_temp) {
  var _ref = _temp === void 0 ? {} : _temp,
    _ref$initialSize = _ref.initialSize,
    initialSize = _ref$initialSize === void 0 ? defaultInitialSize : _ref$initialSize,
    _ref$debounceTime = _ref.debounceTime,
    debounceTime = _ref$debounceTime === void 0 ? 300 : _ref$debounceTime,
    _ref$enableDebounceLe = _ref.enableDebounceLeadingCall,
    enableDebounceLeadingCall = _ref$enableDebounceLe === void 0 ? true : _ref$enableDebounceLe;
  var _useState = useState(initialSize),
    screenSize = _useState[0],
    setScreenSize = _useState[1];
  var handleResize = useMemo(function () {
    return debounce(function () {
      setScreenSize(function () {
        return {
          width: window.innerWidth,
          height: window.innerHeight
        };
      });
    }, debounceTime, {
      leading: enableDebounceLeadingCall
    });
  }, [debounceTime, enableDebounceLeadingCall]);
  useEffect(function () {
    handleResize();
    window.addEventListener('resize', handleResize, false);
    return function () {
      window.removeEventListener('resize', handleResize, false);
      handleResize.cancel();
    };
  }, [handleResize]);
  return screenSize;
};
export default useScreenSize;