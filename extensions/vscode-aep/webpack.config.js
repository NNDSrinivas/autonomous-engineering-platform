//@ts-check
const path = require('path');
/** @type {import('webpack').Configuration} */
module.exports = {
  target: 'node',
  entry: {
    extension: './src/extension.ts',
    'test/runTest': './test/runTest.ts'
  },
  output: {
    path: path.resolve(__dirname, 'out'),
    filename: '[name].js',
    libraryTarget: 'commonjs2'
  },
  devtool: 'source-map',
  externals: { vscode: 'commonjs vscode' },
  resolve: { extensions: ['.ts', '.js'] },
  module: { rules: [{ test: /\.ts$/, exclude: /node_modules/, use: 'ts-loader' }] }
};