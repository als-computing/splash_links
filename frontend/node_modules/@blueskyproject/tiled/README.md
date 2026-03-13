
# Tiled Viewer

A React Tiled Viewer component that can access a Bluesky Tiled server using an api key or auth bearer token. The component can accept a callback function that is run when a user selects an item.



#  Installation
Once you have your own React app setup, install the component in the root project directory with:
```
npm install @blueskyproject/tiled
```

Example usage:
```js
//App.tsx
import { Tiled } from '@blueskyproject/tiled';
import '@blueskyproject/tiled/style.css';

function App() {
  return (
    <Tiled tiledBaseUrl='http://customUrl:port/api/v1' />
  )
}
```

Providing a callback function
```js
//App.tsx
import { Tiled } from '@blueskyproject/tiled';
import '@blueskyproject/tiled/style.css';

const printLinks = (links) => {
  console.log({links});
}

function App() {
  return (
    <Tiled tiledBaseUrl='http://customUrl:port/api/v1' onSelect={printLinks}/>
  )
}
```

You will only need to import '@blueskyproject/tiled/style.css' once.



Hint: To quickly check the props that a component takes on typescript apps, press 'ctrl+space' when clicked inside a component.

# Bluesky Requirements
This component requires a Bluesky Tiled server to be setup and reachable from the host url.

https://github.com/bluesky/tiled

## Common issues connecting to Tiled

A very common issue with making the Tiled React component work properly is improper authorization setup on the Tiled server. There are two main requirements to satisfy.

1. CORS
2. Authentication

CORS issues are solved by instantiating your Tiled server with an allowed origins list. In this list should be the url from which your React website is hosted. You cannot use wildcards in a CORS allow origins list if your tiled server requires an api key (as in not set to public).

Authentication can come in different formats. If you make it past CORS, but you get an authorization error from Tiled Server, then you probably need authentication on the requests. You can add an apiKey prop to <Tiled>, this will add an apiKey parameter to every request to Tiled Server thereafter. You can also add an auth bearer token which will have similar effect. It is most convenient to use a static apiKey during Tiled Server startup.

# Installation - Developer
To check out the project without creating your own React app, or for development, you can pull down the repo and install with npm.

New to React? Make sure you have [npm installed first](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)

## Clone repo and install

```
git clone https://github.com/bluesky/tiled-viewer-react.git
```

```
cd tiled-viewer-react
npm install
```

## Run the dev servers
To start up the react app:
```
npm run dev
```

[localhost:5173](http://localhost:5173)

To start up the storybook server:
```
npm run storybook
```
[localhost:6006](http://localhost:6006)

# Developer Scripts

## Updating the NPM Package
Future configuration will likely support automatic npm builds through gh actions, but currently manual updates are required.

First commit any changes so your working tree is clean

Then increment the package version as appropriate

``` 
npm version patch 
```

Run the build

``` 
npm run build 
```

Publish (token required the first time)

```
npm publish
```

To verify what you're about to publish, you can check out the /dist folder.

The build can be viewed at [https://www.npmjs.com/package/@blueskyproject/tiled](https://www.npmjs.com/package/@blueskyproject/tiled).


