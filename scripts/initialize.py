from brownie import accounts, interface, Contract
from brownie import (Bank, SimpleBankConfig, SimplePriceOracle, PancakeswapGoblin,
                     StrategyAllBNBOnly, StrategyLiquidate, StrategyWithdrawMinimizeTrading, StrategyAddTwoSidesOptimal, PancakeswapGoblinConfig, TripleSlopeModel, ConfigurableInterestBankConfig, PancakeswapPool1Goblin, ProxyAdminImpl, TransparentUpgradeableProxyImpl)
from brownie import network
from .utils import *
from .constant import *
import eth_abi


def test_token_1(bank, goblin, two_side, fToken):
    alice = accounts[1]
    bob = accounts[2]

    bank.deposit({'from': bob, 'value': '2 ether'})

    prevBNBBal = alice.balance()

    bank.work(0, goblin, 10**18, 0, eth_abi.encode_abi(['address', 'bytes'], [two_side.address, eth_abi.encode_abi(
        ['address', 'uint256', 'uint256'], [fToken, 0, 0])]), {'from': alice, 'value': '1 ether'})

    curBNBBal = alice.balance()

    print('∆ bnb alice', curBNBBal - prevBNBBal)

    pos_id = bank.nextPositionID() - 1
    print('alice pos', bank.positionInfo(pos_id))


def test_token(bank, goblin, fToken, add_strat, liq_strat, rem_strat, add_strat_2):
    print('================================================')
    print('Testing')

    alice = accounts[1]
    bob = accounts[2]
    charlie = accounts[3]

    print('goblin', goblin)
    print('fToken', fToken)
    print('add_strat_2', add_strat_2)

    bank.deposit({'from': bob, 'value': '1 ether'})
    bank.deposit({'from': charlie, 'value': '1 ether'})

    prevBNBBal = alice.balance()

    bank.work(0, goblin, 10**18, 0, eth_abi.encode_abi(['address', 'bytes'], [add_strat_2.address,
                                                                              eth_abi.encode_abi(['address', 'uint256', 'uint256'], [fToken, 0, 0])]), {'from': alice, 'value': '1 ether'})

    curBNBBal = alice.balance()

    print('∆ bnb alice', curBNBBal - prevBNBBal)

    pos_id = bank.nextPositionID() - 1
    print('alice pos', bank.positionInfo(pos_id))

    assert almostEqual(curBNBBal - prevBNBBal, -10**18), 'incorrect BNB input amount'

    prevBNBBal = alice.balance()

    bank.work(pos_id, goblin, 0, 2**256-1, eth_abi.encode_abi(['address', 'bytes'], [
              liq_strat.address, eth_abi.encode_abi(['address', 'uint256'], [fToken, 0])]), {'from': alice})

    curBNBBal = alice.balance()

    print('∆ bnb alice', curBNBBal - prevBNBBal)
    print('alice pos', bank.positionInfo(pos_id))

    if fToken == cake_address:
        bank.work(0, goblin, 10**18, 0, eth_abi.encode_abi(['address', 'bytes'], [add_strat_2.address,
                                                                                  eth_abi.encode_abi(['address', 'uint256', 'uint256'], [fToken, 0, 0])]), {'from': alice, 'value': '1 ether'})
    else:
        bank.work(0, goblin, 10**18, 0, eth_abi.encode_abi(['address', 'bytes'], [add_strat.address,
                                                                                  eth_abi.encode_abi(['address', 'uint256'], [fToken, 0])]), {'from': alice, 'value': '1 ether'})

    pos_id = bank.nextPositionID() - 1

    bank.work(pos_id, goblin, 0, 2**256-1, eth_abi.encode_abi(['address', 'bytes'], [
              rem_strat.address, eth_abi.encode_abi(['address', 'uint256'], [fToken, 0])]), {'from': alice})

    print('reinvesting')
    goblin.reinvest({'from': alice})

    print('liquidating')
    bank.work(0, goblin, 10**18, 0, eth_abi.encode_abi(['address', 'bytes'], [add_strat_2.address,
                                                                              eth_abi.encode_abi(['address', 'uint256', 'uint256'], [fToken, 0, 0])]), {'from': alice, 'value': '1 ether'})

    pos_id = bank.nextPositionID() - 1

    pre_bank_bal = bank.balance()

    goblin.liquidate(pos_id, {'from': bank, 'gas_price': 0})

    post_bank_bal = bank.balance()

    print('liq gain', post_bank_bal - pre_bank_bal)
    assert post_bank_bal - pre_bank_bal > 0, 'liq gets 0'


def main():

    deployer = accounts.at('0x4D4DA0D03F6f087697bbf13378a21E8ff6aF1a58', force=True)
    # deployer = accounts.load('ghb')

    triple_slope = TripleSlopeModel.at('0x9b0432c1800f35fd5235d24c2e223c45cefe0864')
    bank_config = ConfigurableInterestBankConfig.at('0x70df43522d3a7332310b233de763758adca14961')
    bank_impl = Bank.at('0x35cfacc93244fc94d26793cd6e68f59976380b3e')
    bank = Bank.at('0x3bb5f6285c312fc7e1877244103036ebbeda193d')
    add_strat = StrategyAllBNBOnly.at('0x06a34a95b3e1064295e93e9c92c15a4ebfed7eef')
    liq_strat = StrategyLiquidate.at('0x034c0d2b94a2b843c3cccae6be0f74f44b5dd3f9')
    rem_strat = StrategyWithdrawMinimizeTrading.at('0xbd1c05cbe5f7c625bb7877caa23ba461abae4887')
    goblin_config = PancakeswapGoblinConfig.at('0x8703f72dbdcd169a9c702e7044603ebbfb11425c')

    cake_goblin = PancakeswapPool1Goblin.at('0xaa00f2b7dd0de46c6fc9655dbadd80ac91a66869')
    busd_goblin = PancakeswapGoblin.at('0x08d871ddad70bd3aef3fecfbf4350debc57d8264')
    btc_goblin = PancakeswapGoblin.at('0x549ef362657a3e3923793a494db3d89e3e5fda35')
    eth_goblin = PancakeswapGoblin.at('0x2f050b64ede3b1d21184435974bb1d2fe02012b6')
    usdt_goblin = PancakeswapGoblin.at('0x3974071481dad49ac94ca1756f311c872ec3e26e')
    alpha_goblin = PancakeswapGoblin.at('0xa0aa119e0324d864831c24b78e85927526e42d52')

    cake_two_side = StrategyAddTwoSidesOptimal.at('0x93db96377706693b0c4548efaddb73dce4a3f14b')
    busd_two_side = StrategyAddTwoSidesOptimal.at('0x1805f590c13ec9c59a197400f56b4b0d1adec796')
    btc_two_side = StrategyAddTwoSidesOptimal.at('0x8240600913c1a8b3d80b29245d94f2af09facac8')
    eth_two_side = StrategyAddTwoSidesOptimal.at('0x40bdfa199ef27143f0ce292a162450cf5512c390')
    usdt_two_side = StrategyAddTwoSidesOptimal.at('0x7fcae7fd3cb010c30751420a2553bc8232923eae')
    alpha_two_side = StrategyAddTwoSidesOptimal.at('0xb8bd068dd234d9cc06763cfbcea53ecd60e82b8d')

    goblins = [cake_goblin, busd_goblin, btc_goblin, eth_goblin, usdt_goblin, alpha_goblin]
    configs = [
        [True, 6250, 7000, 11000],
        [True, 7000, 8000, 11000],
        [True, 7000, 8000, 11000],
        [True, 7000, 8000, 11000],
        [True, 7000, 8000, 11000],
        [True, 6250, 7000, 11000]
    ]

    two_sides = [cake_two_side, busd_two_side, btc_two_side,
                 eth_two_side, usdt_two_side, alpha_two_side]

    tokens = [cake_address, busd_address, btcb_address, eth_address, usdt_address, alpha_address]

    # set goblins
    bank_config.setGoblins(goblins, [goblin_config] * len(goblins), {'from': deployer})

    # set configs
    goblin_config.setConfigs(goblins, configs, {'from': deployer})

    # set strat ok to two_side and rem_strat
    assert len(goblins) == len(two_sides), 'length unequal'

    for i in range(len(goblins)):
        goblin = goblins[i]
        add_strat_2 = two_sides[i]

        goblin.setStrategyOk([add_strat_2, rem_strat], True, {'from': deployer})

        if i == 0:
            goblin.setCriticalStrategies(add_strat_2, liq_strat, {'from': deployer})
            goblin.setStrategyOk([add_strat], False, {'from': deployer})

    add_strat.setWhitelistTokens(tokens[1:], [True] * len(tokens[1:]), {'from': deployer})
    liq_strat.setWhitelistTokens(tokens, [True] * len(tokens), {'from': deployer})
    rem_strat.setWhitelistTokens(tokens, [True] * len(tokens), {'from': deployer})

    #########################################################################
    # test work

    # make sure remaining debt is not too small
    test_token_1(bank, cake_goblin, two_sides[0], tokens[0])

    for i in range(len(goblins)):
        goblin = goblins[i]
        add_strat_2 = two_sides[i]
        fToken = tokens[i]

        test_token(bank, goblin, fToken, add_strat, liq_strat, rem_strat, add_strat_2)