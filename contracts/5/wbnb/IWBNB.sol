// "SPDX-License-Identifier: UNLICENSED
pragma solidity >=0.5.0;

interface IWBNB {
  function deposit() external payable;

  function transfer(address to, uint value) external returns (bool);

  function withdraw(uint) external;
}
